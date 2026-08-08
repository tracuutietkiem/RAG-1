"""evaluate.py — Đánh giá 4 mode của Buổi 09 trên cùng một bộ câu hỏi.

RETRIEVAL-ONLY: tuyệt đối không gọi answer generation. Query expansion và
semantic retrieval CÓ gọi service (người dùng chủ động chạy lệnh này), còn test
offline của evaluator dùng fixture/fake.

Chạy:  python evaluate.py --k 5
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import advanced_rag as ar  # noqa: E402
import hierarchical_rag as hr  # noqa: E402
import rag  # noqa: E402

QUESTIONS_PATH = BASE_DIR / "eval" / "questions.json"
REPORTS_DIR = BASE_DIR / "reports"
DEFAULT_K = 5


# ---------------------------------------------------------------------------
# Metric (binary relevance)
# ---------------------------------------------------------------------------


def recall_at_k(retrieved: list[str], relevant: set, k: int) -> float | None:
    """
    Tỷ lệ tài liệu liên quan xuất hiện trong top-K.

    Trả None (chứ không phải 0.0) khi câu hỏi không có nhãn — 0.0 sẽ bị hiểu
    nhầm là "hệ thống trượt", trong khi thực tế là "không có gì để trượt".
    """
    if not relevant:
        return None
    top = retrieved[:k]
    return len([r for r in top if r in relevant]) / len(relevant)


def mrr_at_k(retrieved: list[str], relevant: set, k: int) -> float | None:
    if not relevant:
        return None
    for i, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set, k: int) -> float | None:
    """nDCG với relevance nhị phân (0/1). IDCG tính trên số nhãn thực có."""
    if not relevant:
        return None
    import math

    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, rid in enumerate(retrieved[:k], start=1)
        if rid in relevant
    )
    ideal_n = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_n + 1))
    return dcg / idcg if idcg else None


def _mean(values) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


def _p50(values) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return statistics.median(vals) if vals else None


# ---------------------------------------------------------------------------
# Question set
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = ("question_id", "question", "question_type", "relevant_child_ids",
                    "relevant_parent_ids", "needs_human_review")


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise rag.DataError(f"Không thấy bộ câu hỏi: {path}") from exc
    except json.JSONDecodeError as exc:
        raise rag.DataError(f"questions.json hỏng: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise rag.DataError("questions.json phải là danh sách không rỗng.")

    seen = set()
    for item in data:
        missing = [f for f in _REQUIRED_FIELDS if f not in item]
        if missing:
            raise rag.DataError(
                f"Câu hỏi {item.get('question_id', '?')} thiếu trường: {', '.join(missing)}"
            )
        if item["question_id"] in seen:
            raise rag.DataError(f"question_id trùng lặp: {item['question_id']}")
        seen.add(item["question_id"])
        item.setdefault("scope", "in_scope")
    return data


def validate_gold_against_store(questions: list[dict], children_by_id: dict,
                                parents_by_id: dict) -> None:
    """
    Nhãn trỏ tới ID không còn tồn tại là nhãn CHẾT — phải fail, không được im
    lặng tính recall trên tập rỗng rồi báo số đẹp.
    """
    problems = []
    for q in questions:
        for cid in q["relevant_child_ids"]:
            if cid not in children_by_id:
                problems.append(f"{q['question_id']}: child '{cid}' không có trong store")
        for pid in q["relevant_parent_ids"]:
            if pid not in parents_by_id:
                problems.append(f"{q['question_id']}: parent '{pid}' không có trong store (stale)")
    if problems:
        raise rag.DataError(
            "Gold labels đã lệch so với hierarchy store hiện tại:\n  - "
            + "\n  - ".join(problems[:20])
            + "\nHãy build lại hierarchy rồi resolve lại parent_id trong eval/questions.json."
        )


# ---------------------------------------------------------------------------
# Đánh giá
# ---------------------------------------------------------------------------


def _retrieved_ids(mode: str, result: dict) -> tuple[list[str], list[str]]:
    """
    Trả (child_ids, parent_ids) theo thứ tự hạng cuối cùng của mode.

    - flat mode: đơn vị cuối là child; parent suy ra từ registry ở hàm gọi.
    - parent mode: đơn vị cuối là parent; child lấy từ supporting children theo
      đúng thứ tự parent để Child Recall so sánh được giữa hai họ mode.
    """
    final = result.get("reranked", [])
    if mode in hr.PARENT_MODES:
        parent_ids = [p["parent_id"] for p in final]
        child_ids = []
        for p in final:
            for cid in p.get("supporting_child_ids", []):
                if cid not in child_ids:
                    child_ids.append(cid)
        return child_ids, parent_ids
    return [c["chunk_id"] for c in final], []


def evaluate(
    k: int = DEFAULT_K,
    modes: tuple = hr.VALID_MODES,
    questions_path: Path = QUESTIONS_PATH,
    chunks_dir: Path = rag.CHUNKS_DIR,
    persist_path: Path = rag.CHROMA_DIR,
    hierarchy_dir: Path = hr.HIERARCHY_DIR,
    config=None,
    hcfg=None,
    hybrid_fn=None,
    rerank_scorer=None,
    query_generator_fn=None,
    embed_client_factory=None,
) -> dict:
    """Chạy từng câu hỏi qua từng mode, retrieval-only."""
    import time

    config = config or ar.load_advanced_config()
    hcfg = hcfg or hr.load_hierarchy_config()
    questions = load_questions(questions_path)

    children_by_id, parents_by_id, manifest = hr.load_hierarchy_store(hierarchy_dir)
    validate_gold_against_store(questions, children_by_id, parents_by_id)

    index = None
    if hybrid_fn is None:
        chunks, _ = rag.load_chunks(input_dir=chunks_dir, strategy=hr.STRATEGY)
        index = ar.build_bm25_index(chunks)

    per_question = []
    failures = []

    for q in questions:
        row = {
            "question_id": q["question_id"],
            "question": q["question"],
            "question_type": q["question_type"],
            "scope": q["scope"],
            "needs_human_review": q["needs_human_review"],
            "relevant_child_count": len(q["relevant_child_ids"]),
            "relevant_parent_count": len(q["relevant_parent_ids"]),
            "by_mode": {},
        }
        gold_children = set(q["relevant_child_ids"])
        gold_parents = set(q["relevant_parent_ids"])

        for mode in modes:
            t0 = time.perf_counter()
            try:
                res = hr.retrieve_for_hierarchical_mode(
                    q["question"], mode, config, hcfg,
                    chunks_dir=chunks_dir, persist_path=persist_path,
                    hierarchy_dir=hierarchy_dir, bm25_index=index,
                    query_generator_fn=query_generator_fn,
                    embed_client_factory=embed_client_factory,
                    hybrid_fn=hybrid_fn, rerank_scorer=rerank_scorer,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append({"question_id": q["question_id"], "mode": mode,
                                 "error": str(exc)[:300]})
                row["by_mode"][mode] = {"status": "error", "error": str(exc)[:300]}
                continue
            latency_ms = (time.perf_counter() - t0) * 1000.0

            child_ids, parent_ids = _retrieved_ids(mode, res)
            if mode not in hr.PARENT_MODES:
                # flat mode: quy đổi child -> parent để so cùng thang với parent mode.
                parent_ids = []
                for cid in child_ids:
                    pid = (children_by_id.get(cid) or {}).get("parent_id")
                    if pid and pid not in parent_ids:
                        parent_ids.append(pid)

            final = res.get("reranked", [])
            context_chars = sum(len(f.get("text") or "") for f in final)
            child_chars = sum(len(h.get("text") or "") for h in res.get("child_hits", []))

            row["by_mode"][mode] = {
                "status": res.get("status"),
                "child_recall_at_k": recall_at_k(child_ids, gold_children, k),
                "parent_recall_at_k": recall_at_k(parent_ids, gold_parents, k),
                "mrr_at_k": mrr_at_k(
                    parent_ids if mode in hr.PARENT_MODES else child_ids,
                    gold_parents if mode in hr.PARENT_MODES else gold_children, k),
                "ndcg_at_k": ndcg_at_k(
                    parent_ids if mode in hr.PARENT_MODES else child_ids,
                    gold_parents if mode in hr.PARENT_MODES else gold_children, k),
                "unique_relevant_parents": len(set(parent_ids[:k]) & gold_parents),
                "unique_sources": len({f.get("source") for f in final if f.get("source")}),
                "query_count": len(res["query_set"]["queries"]),
                "child_union_count": len(res.get("child_hits", [])),
                "final_count": len(final),
                "context_chars": context_chars,
                "expansion_factor": (context_chars / child_chars) if child_chars else None,
                "generation_api_calls": res.get("generation_api_calls", 0),
                "embedding_api_calls": res.get("embedding_api_calls", 0),
                "latency_ms": latency_ms,
            }
        per_question.append(row)

    # --- tổng hợp: CHỈ câu in_scope mới vào metric chất lượng ---
    scored = [r for r in per_question if r["scope"] == "in_scope"]
    aggregate = {}
    for mode in modes:
        rows = [r["by_mode"].get(mode, {}) for r in scored]
        ok = [x for x in rows if x.get("status") and x.get("status") != "error"]
        all_rows = [r["by_mode"].get(mode, {}) for r in per_question]
        all_ok = [x for x in all_rows if x.get("status") and x.get("status") != "error"]
        aggregate[mode] = {
            "questions_scored": len(ok),
            "questions_run": len(all_ok),
            "questions_failed": len(all_rows) - len(all_ok),
            "child_recall_at_k": _mean(x.get("child_recall_at_k") for x in ok),
            "parent_recall_at_k": _mean(x.get("parent_recall_at_k") for x in ok),
            "mrr_at_k": _mean(x.get("mrr_at_k") for x in ok),
            "ndcg_at_k": _mean(x.get("ndcg_at_k") for x in ok),
            "query_count_mean": _mean(x.get("query_count") for x in all_ok),
            "child_union_count_mean": _mean(x.get("child_union_count") for x in all_ok),
            "context_chars_mean": _mean(x.get("context_chars") for x in all_ok),
            "expansion_factor_mean": _mean(x.get("expansion_factor") for x in all_ok),
            "generation_api_calls_total": sum(x.get("generation_api_calls", 0) for x in all_ok),
            "embedding_api_calls_total": sum(x.get("embedding_api_calls", 0) for x in all_ok),
            "latency_ms": {
                "mean": _mean(x.get("latency_ms") for x in all_ok),
                "p50": _p50(x.get("latency_ms") for x in all_ok),
            },
        }

    needs_review = sum(1 for q in questions if q["needs_human_review"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "modes": list(modes),
        "identities": {
            "embedding_model": config.base.embedding_model,
            "generation_model": config.base.generation_model,
            "reranker_model": config.reranker_model,
            "strategy": hr.STRATEGY,
            "hierarchy_built_at": manifest.get("built_at"),
            "hierarchy_counts": manifest.get("counts"),
            "corpus_files": manifest.get("input_files"),
            "config": {
                "MULTI_QUERY_COUNT": hcfg.multi_query_count,
                "PER_QUERY_CANDIDATES": hcfg.per_query_candidates,
                "PARENT_RRF_K": hcfg.parent_rrf_k,
                "PARENT_SCORE_CHILD_LIMIT": hcfg.parent_score_child_limit,
                "PARENT_CANDIDATES": hcfg.parent_candidates,
                "FINAL_PARENT_TOP_K": hcfg.final_parent_top_k,
                "RERANK_MIN_SCORE": config.rerank_min_score,
            },
        },
        "question_counts": {
            "total": len(questions),
            "in_scope": len(scored),
            "out_of_scope": len(questions) - len(scored),
        },
        "needs_human_review_count": needs_review,
        "human_review_warning": (
            f"{needs_review}/{len(questions)} câu hỏi có needs_human_review=true. "
            "Số liệu chỉ để tham khảo nội bộ; KHÔNG dùng để kết luận mode nào tốt hơn "
            "cho tới khi nhãn được người có chuyên môn xác nhận."
        ) if needs_review else None,
        "generation_called": False,
        "per_question": per_question,
        "per_mode": aggregate,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def save_report(report: dict, reports_dir: Path = REPORTS_DIR) -> Path:
    """
    Ghi atomically. `latest_report.json` CHỈ được cập nhật sau khi report chính
    đã ghi xong và hợp lệ — nếu không, lần chạy hỏng sẽ trỏ latest vào file rác.
    """
    for field in ("timestamp", "per_mode", "per_question", "identities"):
        if field not in report:
            raise rag.DataError(f"Report thiếu '{field}' — không ghi.")

    rd = Path(reports_dir)
    rd.mkdir(parents=True, exist_ok=True)
    stamp = report["timestamp"].replace(":", "").replace("-", "")[:15]
    path = rd / f"eval_{stamp}.json"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)

    latest = rd / "latest_report.json"
    tmp2 = latest.with_suffix(".json.tmp")
    tmp2.write_text(payload, encoding="utf-8")
    os.replace(tmp2, latest)
    return path


def _fmt(v, nd=4):
    return "—" if v is None else f"{v:.{nd}f}"


def _print_report(report: dict) -> None:
    print(f"Evaluation Buổi 09 — K={report['k']}")
    ids = report["identities"]
    print(f"Corpus: {ids['hierarchy_counts']} | hierarchy build: {ids['hierarchy_built_at']}")
    qc = report["question_counts"]
    print(f"Câu hỏi: {qc['total']} (in_scope {qc['in_scope']}, out_of_scope {qc['out_of_scope']})")
    print()
    header = (f"{'mode':<15}{'ChildR@K':>10}{'ParentR@K':>11}{'MRR@K':>9}{'nDCG@K':>9}"
              f"{'ctx chars':>11}{'mở rộng':>9}{'ms p50':>9}")
    print(header)
    print("-" * len(header))
    for mode in report["modes"]:
        m = report["per_mode"][mode]
        print(f"{mode:<15}{_fmt(m['child_recall_at_k']):>10}{_fmt(m['parent_recall_at_k']):>11}"
              f"{_fmt(m['mrr_at_k']):>9}{_fmt(m['ndcg_at_k']):>9}"
              f"{_fmt(m['context_chars_mean'],0):>11}{_fmt(m['expansion_factor_mean'],2):>9}"
              f"{_fmt(m['latency_ms']['p50'],0):>9}")
    print()
    print(f"{'mode':<15}{'gen call':>10}{'embed call':>12}{'query TB':>10}{'child union TB':>16}")
    for mode in report["modes"]:
        m = report["per_mode"][mode]
        print(f"{mode:<15}{m['generation_api_calls_total']:>10}{m['embedding_api_calls_total']:>12}"
              f"{_fmt(m['query_count_mean'],1):>10}{_fmt(m['child_union_count_mean'],1):>16}")
    print()
    if report.get("human_review_warning"):
        print("⚠ " + report["human_review_warning"])
    if report["failures"]:
        print(f"\n{len(report['failures'])} lượt lỗi:")
        for f in report["failures"][:10]:
            print(f"  [{f['question_id']}/{f['mode']}] {f['error'][:120]}")
    print("\nEvaluation là RETRIEVAL-ONLY: không gọi answer generation "
          f"(generation_called={report['generation_called']}).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluation 4 mode — Buổi 09")
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--modes", default=",".join(hr.VALID_MODES))
    parser.add_argument("--no-save", action="store_true", help="Chỉ in, không ghi report")
    args = parser.parse_args()

    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    invalid = [m for m in modes if m not in hr.VALID_MODES]
    if invalid:
        print(f"[LỖI] mode không hợp lệ: {', '.join(invalid)}")
        return 1

    try:
        report = evaluate(k=args.k, modes=modes)
    except (rag.DataError, rag.EmbeddingError, rag.ChromaError,
            hr.HierarchyError, ar.AdvancedConfigError) as exc:
        print(f"[LỖI] {exc}")
        return 1
    except hr.HierarchyNotReadyError as exc:
        print(f"[CHƯA SẴN SÀNG] {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[LỖI] Không chạy được evaluation: {exc}")
        return 1

    _print_report(report)
    if not args.no_save:
        path = save_report(report)
        print(f"\nĐã ghi: {path}")
        print(f"Đã cập nhật: {path.parent / 'latest_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
