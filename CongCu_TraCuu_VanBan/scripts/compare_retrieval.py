#!/usr/bin/env python3
"""
PROMPT 5 - Danh gia BM25 vs Dense vs Hybrid vs Hybrid+Rerank.

Cung corpus, cung bo cau hoi, cung evaluation protocol.
Khong doi gold de ket qua dep hon. Khong bo query that bai.

Output:
    buoi_14/outputs/retrieval_comparison.csv
    buoi_14/outputs/evaluation_report.md
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import corpus, pipeline  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

METHODS = ["bm25", "dense", "hybrid", "hybrid_rerank"]
CUTOFFS = [1, 3, 5]


def load_questions() -> list[dict]:
    if not config.QUESTIONS_CSV.exists():
        raise FileNotFoundError(
            f"Chua co {config.QUESTIONS_CSV}. Chay: python scripts/build_questions.py"
        )
    with open(config.QUESTIONS_CSV, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--candidate-k", type=int, default=config.CANDIDATE_K)
    args = ap.parse_args()

    questions = load_questions()
    index = corpus.chunk_index()
    backend = pipeline.backend_info()

    rows: list[dict] = []
    errors: list[dict] = []

    for q in questions:
        gold = q["expected_chunk_id"]
        gold_ok = gold in index
        for method in METHODS:
            try:
                out = pipeline.retrieve(
                    q["question"], method=method,
                    top_k=args.top_k, candidate_k=args.candidate_k,
                )
                hits = [r["chunk_id"] for r in out["results"]]
                gold_rank = hits.index(gold) + 1 if gold in hits else 0
                gold_doc = index[gold]["document_id"] if gold_ok else ""
                doc_hits = [
                    index[c]["document_id"] for c in hits if c in index
                ]
                doc_rank = doc_hits.index(gold_doc) + 1 if gold_doc in doc_hits else 0
                rows.append(
                    {
                        "question_id": q["question_id"],
                        "query_type": q["query_type"],
                        "question": q["question"],
                        "method": method,
                        "expected_chunk_id": gold,
                        "gold_rank": gold_rank,
                        "gold_doc_rank": doc_rank,
                        "hit@1": int(gold_rank == 1),
                        "hit@3": int(0 < gold_rank <= 3),
                        "hit@5": int(0 < gold_rank <= 5),
                        "rr": round(1.0 / gold_rank, 6) if gold_rank else 0.0,
                        "top1_chunk_id": hits[0] if hits else "",
                        "error": "",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                errors.append({"question_id": q["question_id"], "method": method,
                               "error": f"{type(exc).__name__}: {exc}"})
                rows.append(
                    {
                        "question_id": q["question_id"], "query_type": q["query_type"],
                        "question": q["question"], "method": method,
                        "expected_chunk_id": gold, "gold_rank": 0, "gold_doc_rank": 0,
                        "hit@1": 0, "hit@3": 0, "hit@5": 0, "rr": 0.0,
                        "top1_chunk_id": "", "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    out_csv = config.OUTPUTS_DIR / "retrieval_comparison.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---------------- tong hop ----------------
    def agg(subset: list[dict]) -> dict:
        res = {}
        for m in METHODS:
            sub = [r for r in subset if r["method"] == m]
            n = len(sub) or 1
            res[m] = {
                "n": len(sub),
                **{f"hit@{k}": sum(r[f'hit@{k}'] for r in sub) / n for k in CUTOFFS},
                "mrr": sum(r["rr"] for r in sub) / n,
                "doc_hit@5": sum(1 for r in sub if 0 < r["gold_doc_rank"] <= 5) / n,
            }
        return res

    overall = agg(rows)
    by_type = {t: agg([r for r in rows if r["query_type"] == t])
               for t in sorted({r["query_type"] for r in rows})}

    # ---------------- bao cao ----------------
    L: list[str] = []
    add = L.append
    add("# Bao cao danh gia Retrieval - Buoi 14\n")
    type_counts = ", ".join(
        "{}={}".format(t, sum(1 for q in questions if q["query_type"] == t))
        for t in by_type
    )
    add(f"- So cau hoi: **{len(questions)}** ({type_counts})")
    add(f"- Corpus: `data/processed/chunks_normalized.csv` "
        f"({len(index)} chunk / {len({v['document_id'] for v in index.values()})} van ban)")
    add(f"- top_k = {args.top_k}, candidate_k = {args.candidate_k}, RRF_K = {config.RRF_K}\n")

    add("## 0. Backend thuc te da dung (khong giau)\n")
    add(f"- Dense: `{backend['dense_backend']}` — "
        f"**{'NEURAL' if backend['dense_is_neural'] else 'FALLBACK, KHONG phai neural embedding'}**")
    add(f"  - {backend['dense_detail']}")
    add(f"- Reranker: `{backend['rerank_backend']}` — "
        f"**{'NEURAL' if backend['rerank_is_neural'] else 'FALLBACK, KHONG phai neural cross-encoder'}**")
    add(f"  - {backend['rerank_detail']}\n")
    if not backend["dense_is_neural"] or not backend["rerank_is_neural"]:
        add("> Ket qua duoi day phai doc kem dieu kien nay. Khi chay tren may co tai duoc\n"
            "> model tu HuggingFace, dat `DENSE_BACKEND=sentence_transformers` va\n"
            "> `RERANKER_BACKEND=cross_encoder` roi chay lai de co so lieu neural that.\n")

    add("## 1. Ket qua tong the\n")
    add("| Cau hinh | Hit@1 | Hit@3 | Hit@5 | MRR@5 | Dung van ban @5 |")
    add("|---|---|---|---|---|---|")
    for m in METHODS:
        s = overall[m]
        add(f"| `{m}` | {s['hit@1']:.3f} | {s['hit@3']:.3f} | {s['hit@5']:.3f} | "
            f"{s['mrr']:.3f} | {s['doc_hit@5']:.3f} |")
    add("")

    add("## 2. Ket qua theo loai cau hoi\n")
    for t, res in by_type.items():
        add(f"### {t}\n")
        add("| Cau hinh | Hit@1 | Hit@3 | Hit@5 | MRR@5 |")
        add("|---|---|---|---|---|")
        for m in METHODS:
            s = res[m]
            add(f"| `{m}` | {s['hit@1']:.3f} | {s['hit@3']:.3f} | {s['hit@5']:.3f} | {s['mrr']:.3f} |")
        add("")

    add("## 3. Nhan xet\n")
    ek = by_type.get("EXACT_KEYWORD", {})
    se = by_type.get("SEMANTIC", {})
    if ek:
        best = max(METHODS, key=lambda m: ek[m]["mrr"])
        add(f"- Nhom **EXACT_KEYWORD** (co so hieu van ban + so dieu): manh nhat la `{best}` "
            f"(MRR {ek[best]['mrr']:.3f}); BM25 dat MRR {ek['bm25']['mrr']:.3f}, "
            f"Dense dat {ek['dense']['mrr']:.3f}. "
            f"Day dung ky vong: ma van ban la tin hieu tu khoa chinh xac, BM25 khai thac truc tiep.")
    if se:
        best = max(METHODS, key=lambda m: se[m]["mrr"])
        add(f"- Nhom **SEMANTIC** (khong chua so hieu): manh nhat la `{best}` "
            f"(MRR {se[best]['mrr']:.3f}); BM25 {se['bm25']['mrr']:.3f}, Dense {se['dense']['mrr']:.3f}.")
    add(f"- **Hybrid co giup khong:** Hybrid MRR {overall['hybrid']['mrr']:.3f} so voi "
        f"BM25 {overall['bm25']['mrr']:.3f} va Dense {overall['dense']['mrr']:.3f}.")
    changed = sum(
        1 for qid in {r["question_id"] for r in rows}
        if next(r for r in rows if r["question_id"] == qid and r["method"] == "hybrid")["top1_chunk_id"]
        != next(r for r in rows if r["question_id"] == qid and r["method"] == "hybrid_rerank")["top1_chunk_id"]
    )
    add(f"- **Reranking co doi ranking khong:** doi vi tri #1 o **{changed}/{len(questions)}** cau hoi. "
        f"MRR sau rerank: {overall['hybrid_rerank']['mrr']:.3f}.")
    add("")

    add("## 4. Failure cases (khong bo query nao)\n")
    fails = [r for r in rows if r["method"] == "hybrid_rerank" and r["gold_rank"] == 0]
    if fails:
        add("| question_id | Loai | Cau hoi | gold | Van ban dung nam trong top5? |")
        add("|---|---|---|---|---|")
        for r in fails:
            add(f"| {r['question_id']} | {r['query_type']} | {r['question'][:60]} | "
                f"`{r['expected_chunk_id']}` | {'co' if r['gold_doc_rank'] else 'khong'} |")
    else:
        add("Khong co cau hoi nao truot hoan toan o cau hinh `hybrid_rerank`.")
    add("")
    if errors:
        add("### Loi khi chay\n")
        for e in errors:
            add(f"- {e['question_id']} / {e['method']}: `{e['error']}`")
        add("")

    add("## 5. Gioi han cua ket luan\n")
    add(f"- Bo cau hoi chi {len(questions)} cau, sinh tu dinh dang co san cua van ban "
        "(so hieu + tieu de Dieu), nen **khong dai dien cho cau hoi tu nhien cua nguoi dung that**.")
    add("- Moi cau hoi chi co DUNG MOT gold chunk. Thuc te nhieu Dieu khac cung co the tra loi dung, "
        "nen Hit@k o day la **can duoi** cua chat luong that.")
    add("- Cau hoi SEMANTIC van tai su dung nguyen van tieu de Dieu, nen con loi the tu vung; "
        "muon do dung han phai co cau hoi do nguoi dung viet lai bang ngon ngu cua ho.")
    if not backend["dense_is_neural"]:
        add("- Dense dang chay FALLBACK (TF-IDF+SVD), **khong** phai embedding neural, "
            "nen so lieu cot `dense` va `hybrid` chua phan anh dung suc manh semantic.")
    add("")

    report = config.OUTPUTS_DIR / "evaluation_report.md"
    report.write_text("\n".join(L), encoding="utf-8")

    print("=" * 78)
    print("EVALUATION")
    print("=" * 78)
    print(f"{'Method':<16}{'Hit@1':>8}{'Hit@3':>8}{'Hit@5':>8}{'MRR@5':>8}")
    for m in METHODS:
        s = overall[m]
        print(f"{m:<16}{s['hit@1']:>8.3f}{s['hit@3']:>8.3f}{s['hit@5']:>8.3f}{s['mrr']:>8.3f}")
    print()
    print(f"Loi khi chay: {len(errors)}")
    print(f"Da ghi: {out_csv.relative_to(config.BASE_DIR)}")
    print(f"Da ghi: {report.relative_to(config.BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
