"""evaluate.py — Đánh giá retrieval (Recall@K, MRR@K, nDCG@K) cho Buổi 08.

Chạy cùng corpus / cùng câu hỏi / cùng k cho MỌI mode để so sánh công bằng.
TUYỆT ĐỐI không gọi generation (chỉ đo chất lượng retrieval, không tốn quota
sinh văn bản).

Gold labels lấy từ `eval/questions.json`. Nếu bất kỳ câu hỏi nào còn
`needs_human_review: true`, report sẽ mang cảnh báo và KHÔNG được dùng để
tuyên bố mode nào chiến thắng chính thức.

Xem SPEC_buoi_08.md mục 10.

CLI:

    <PYTHON> evaluate.py --strategy hierarchical --k 5
    <PYTHON> evaluate.py --strategy hierarchical --k 5 --modes bm25,semantic
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import advanced_rag as ar
import rag

BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = BASE_DIR / "eval" / "questions.json"
REPORTS_DIR = BASE_DIR / "reports"

REQUIRED_QUESTION_FIELDS = ("query_id", "question", "relevant_chunk_ids", "scope", "needs_human_review")


# ---------------------------------------------------------------------------
# Metrics — công thức thuần, không phụ thuộc pipeline (dễ test bằng ví dụ tính tay)
# ---------------------------------------------------------------------------


def recall_at_k(retrieved_ids: list[str], relevant_ids: set, k: int) -> float:
    """
    Tỉ lệ tài liệu liên quan được tìm thấy trong top-k.

    Không có tài liệu liên quan nào (câu hỏi out-of-scope) -> trả 0.0 và cần
    được xử lý riêng ở tầng gọi, vì recall không có ý nghĩa khi mẫu số bằng 0.
    """
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    found = sum(1 for cid in relevant_ids if cid in top_k)
    return found / len(relevant_ids)


def mrr_at_k(retrieved_ids: list[str], relevant_ids: set, k: int) -> float:
    """Nghịch đảo thứ hạng của tài liệu liên quan ĐẦU TIÊN trong top-k (0 nếu không có)."""
    if not relevant_ids:
        return 0.0
    for rank, cid in enumerate(retrieved_ids[:k], start=1):
        if cid in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set, k: int) -> float:
    """
    nDCG@K với binary relevance (liên quan = 1, không liên quan = 0).

        DCG  = sum( rel_i / log2(i + 1) ) với i tính từ 1
        IDCG = DCG của thứ hạng lý tưởng (mọi tài liệu liên quan xếp đầu)
        nDCG = DCG / IDCG
    """
    if not relevant_ids:
        return 0.0
    dcg = 0.0
    for i, cid in enumerate(retrieved_ids[:k], start=1):
        if cid in relevant_ids:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Gold labels
# ---------------------------------------------------------------------------


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    """Đọc + validate gold labels. Lỗi dữ liệu phải báo rõ, không bỏ qua âm thầm."""
    if not path.exists():
        raise rag.DataError(f"Không tìm thấy file câu hỏi đánh giá: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise rag.DataError(f"File '{path.name}' không phải JSON hợp lệ: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise rag.DataError(f"File '{path.name}' phải là JSON list không rỗng.")

    seen_ids = set()
    for i, q in enumerate(data):
        if not isinstance(q, dict):
            raise rag.DataError(f"Câu hỏi vị trí {i} phải là JSON object.")
        missing = [f for f in REQUIRED_QUESTION_FIELDS if f not in q]
        if missing:
            raise rag.DataError(f"Câu hỏi vị trí {i} thiếu field bắt buộc {missing}.")
        if not isinstance(q["question"], str) or not q["question"].strip():
            raise rag.DataError(f"Câu hỏi vị trí {i}: field 'question' phải là string không rỗng.")
        if not isinstance(q["relevant_chunk_ids"], list):
            raise rag.DataError(f"Câu hỏi vị trí {i}: 'relevant_chunk_ids' phải là list.")
        if q["scope"] not in ("in_scope", "out_of_scope"):
            raise rag.DataError(
                f"Câu hỏi vị trí {i}: 'scope' chỉ nhận 'in_scope' hoặc 'out_of_scope', nhận {q['scope']!r}."
            )
        if q["query_id"] in seen_ids:
            raise rag.DataError(f"query_id trùng lặp: {q['query_id']!r}.")
        seen_ids.add(q["query_id"])
    return data


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    questions: list[dict],
    config: ar.AdvancedConfig,
    strategy: str,
    k: int,
    modes: tuple = ar.VALID_MODES,
    chunks_dir: Path = rag.CHUNKS_DIR,
    persist_path: Path = rag.CHROMA_DIR,
    embed_client_factory=None,
    rerank_scorer=None,
) -> dict:
    """
    Chạy retrieval (KHÔNG generation) cho mọi mode trên cùng tập câu hỏi.

    Câu hỏi `out_of_scope` không có tài liệu liên quan nên không tính vào
    Recall/MRR/nDCG (mẫu số bằng 0 sẽ làm sai lệch trung bình). Thay vào đó
    chúng được đếm riêng ở `out_of_scope_count` để người đọc tự đánh giá
    false-positive.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise rag.DataError(f"k phải là số nguyên >= 1, nhận {k!r}.")

    # BM25 index dựng MỘT lần, dùng chung cho mọi mode và mọi câu hỏi.
    chunks, _stats = rag.load_chunks(input_dir=chunks_dir, strategy=strategy)
    index = ar.build_bm25_index(chunks)

    in_scope = [q for q in questions if q["scope"] == "in_scope"]
    out_scope = [q for q in questions if q["scope"] == "out_of_scope"]

    metrics_by_mode: dict[str, dict] = {}
    per_query: dict[str, list] = {}
    failures: list[dict] = []

    for mode in modes:
        recalls, mrrs, ndcgs, latencies = [], [], [], []
        rows = []
        for q in questions:
            try:
                retrieval = ar.retrieve_for_mode(
                    q["question"], mode, config, strategy, bm25_index=index,
                    chunks_dir=chunks_dir, persist_path=persist_path,
                    embed_client_factory=embed_client_factory, rerank_scorer=rerank_scorer,
                )
            except Exception as exc:
                failures.append({"mode": mode, "query_id": q["query_id"], "error": str(exc)})
                continue

            retrieved_ids = [c["chunk_id"] for c in retrieval["candidates"]]
            relevant = set(q["relevant_chunk_ids"])
            latency = retrieval["latency_ms"]["total"]
            latencies.append(latency)

            row = {
                "query_id": q["query_id"],
                "scope": q["scope"],
                "retrieved_ids": retrieved_ids,
                "latency_ms": latency,
            }
            if q["scope"] == "in_scope":
                r = recall_at_k(retrieved_ids, relevant, k)
                m = mrr_at_k(retrieved_ids, relevant, k)
                n = ndcg_at_k(retrieved_ids, relevant, k)
                recalls.append(r)
                mrrs.append(m)
                ndcgs.append(n)
                row.update({"recall": r, "mrr": m, "ndcg": n})
            rows.append(row)

        per_query[mode] = rows
        metrics_by_mode[mode] = {
            f"recall@{k}": round(statistics.fmean(recalls), 4) if recalls else None,
            f"mrr@{k}": round(statistics.fmean(mrrs), 4) if mrrs else None,
            f"ndcg@{k}": round(statistics.fmean(ndcgs), 4) if ndcgs else None,
            "latency_mean_ms": round(statistics.fmean(latencies), 1) if latencies else None,
            "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else None,
            "queries_scored": len(recalls),
            "queries_failed": sum(1 for f in failures if f["mode"] == mode),
        }

    needs_review = any(q.get("needs_human_review") for q in questions)
    warnings = []
    if needs_review:
        warnings.append(
            "Gold labels còn 'needs_human_review: true' — bộ nhãn CHƯA được chuyên gia pháp lý "
            "duyệt. Không dùng report này để tuyên bố mode nào chiến thắng chính thức."
        )
    if failures:
        warnings.append(f"Có {len(failures)} lượt chạy lỗi — xem mục 'failures'.")
    if len(in_scope) < 5:
        warnings.append(
            f"Chỉ có {len(in_scope)} câu hỏi in_scope — cỡ mẫu quá nhỏ để kết luận thống kê."
        )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "k": k,
        "modes": list(modes),
        "corpus_size": len(chunks),
        "question_count": len(questions),
        "in_scope_count": len(in_scope),
        "out_of_scope_count": len(out_scope),
        "needs_human_review": needs_review,
        "config": {
            "embedding_model": config.base.embedding_model,
            "embedding_dim": config.base.embedding_dim,
            "reranker_model": config.reranker_model,
            "rerank_device": config.rerank_device,
            "bm25_candidates": config.bm25_candidates,
            "semantic_candidates": config.semantic_candidates,
            "rrf_k": config.rrf_k,
            "rrf_bm25_weight": config.rrf_bm25_weight,
            "rrf_semantic_weight": config.rrf_semantic_weight,
            "rerank_candidates": config.rerank_candidates,
            "final_top_k": config.final_top_k,
            "rerank_min_score": config.rerank_min_score,
            "max_distance": config.base.max_distance,
        },
        "metrics_by_mode": metrics_by_mode,
        "per_query": per_query,
        "failures": failures,
        "warnings": warnings,
        "generation_called": False,
    }


def save_report(report: dict, reports_dir: Path = REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = report["timestamp"].replace(":", "-").replace("+00:00", "Z")
    path = reports_dir / f"eval_{report['strategy']}_k{report['k']}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _print_report(report: dict) -> None:
    print(f"Đánh giá retrieval — strategy: {report['strategy']} | k={report['k']}")
    print(f"Corpus: {report['corpus_size']} chunk | Câu hỏi: {report['question_count']} "
          f"({report['in_scope_count']} in_scope, {report['out_of_scope_count']} out_of_scope)")
    print("KHÔNG gọi generation trong quá trình đánh giá.")
    print()

    k = report["k"]
    header = f"{'mode':<16} {'recall@'+str(k):>10} {'mrr@'+str(k):>9} {'ndcg@'+str(k):>10} {'mean ms':>9} {'p50 ms':>9}"
    print(header)
    print("-" * len(header))
    for mode, m in report["metrics_by_mode"].items():
        def _f(v):
            return f"{v:.4f}" if isinstance(v, (int, float)) else "-"
        def _t(v):
            return f"{v:.1f}" if isinstance(v, (int, float)) else "-"
        print(f"{mode:<16} {_f(m[f'recall@{k}']):>10} {_f(m[f'mrr@{k}']):>9} "
              f"{_f(m[f'ndcg@{k}']):>10} {_t(m['latency_mean_ms']):>9} {_t(m['latency_p50_ms']):>9}")

    if report["failures"]:
        print()
        print("Lượt chạy lỗi:")
        for f in report["failures"]:
            print(f"  - {f['mode']} / {f['query_id']}: {f['error']}")

    if report["warnings"]:
        print()
        print("CẢNH BÁO:")
        for w in report["warnings"]:
            print(f"  - {w}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Đánh giá retrieval Buổi 08 (không gọi generation)")
    parser.add_argument("--strategy", default=rag.DEFAULT_STRATEGY, choices=rag.VALID_STRATEGIES)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--modes", default=",".join(ar.VALID_MODES),
                        help="Danh sách mode, phân tách bằng dấu phẩy")
    args = parser.parse_args()

    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    invalid = [m for m in modes if m not in ar.VALID_MODES]
    if invalid:
        print(f"[LỖI] Mode không hợp lệ: {invalid} (chỉ nhận {', '.join(ar.VALID_MODES)})")
        return 1

    try:
        config = ar.load_advanced_config()
    except ar.AdvancedConfigError as exc:
        print(f"[LỖI CẤU HÌNH] {exc}")
        return 1

    try:
        questions = load_questions()
        report = evaluate(questions, config, args.strategy, args.k, modes=modes)
    except (rag.DataError, rag.EmbeddingError, rag.ChromaError) as exc:
        print(f"[LỖI] {exc}")
        return 1
    except Exception as exc:
        print(f"[LỖI] Không chạy được đánh giá: {exc}")
        return 1

    _print_report(report)
    path = save_report(report)
    print()
    print(f"Đã lưu report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
