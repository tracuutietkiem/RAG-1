#!/usr/bin/env python3
"""
Sinh buoi_14/outputs/retrieval_examples.md

Chay CUNG mot bo query qua ca 4 cau hinh (BM25 / Dense / Hybrid / Hybrid+Rerank)
de hoc vien thay truc tiep bon bang xep hang khac nhau o cho nao.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import pipeline  # noqa: E402

QUERIES = [
    ("EXACT_KEYWORD",
     "Thông tư 01/2014/TT-NHNN Điều 72 quy định nội dung gì?",
     "Cau hoi chua ma van ban va so dieu cu the -> loi the cua BM25."),
    ("SEMANTIC",
     "Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức cho một khách hàng?",
     "Cau hoi dien dat theo nghiep vu, khong chua ma van ban -> can tin hieu ngu nghia."),
    ("MIXED",
     "Theo Luật Các tổ chức tín dụng 32/2024/QH15, điều kiện để được cấp giấy phép thành lập ngân hàng là gì?",
     "Vua co so hieu van ban vua dien dat theo noi dung."),
]

TOP_K = 5
CANDIDATE_K = 20


def table(results: list[dict], method: str) -> list[str]:
    L = ["", f"**{method}**", ""]
    if method == "Hybrid (RRF)":
        L += ["| # | chunk_id | bm25_rank | dense_rank | rrf_score | citation |",
              "|---|---|---|---|---|---|"]
        for r in results:
            bm = r.get("bm25_rank") or "-"
            dn = r.get("dense_rank") or "-"
            L.append(f"| {r['rank']} | `{r['chunk_id']}` | {bm} | {dn} | "
                     f"{r.get('rrf_score', 0):.6f} | {r['citation'][:70]} |")
    elif method.startswith("Hybrid + Rerank"):
        L += ["| # | chunk_id | hybrid_rank | hybrid_score | rerank_score | citation |",
              "|---|---|---|---|---|---|"]
        for r in results:
            L.append(f"| {r['rank']} | `{r['chunk_id']}` | {r.get('hybrid_rank', '-')} | "
                     f"{r.get('hybrid_score', 0):.6f} | {r.get('rerank_score', 0):.6f} | "
                     f"{r['citation'][:70]} |")
    else:
        L += ["| # | chunk_id | score | citation |", "|---|---|---|---|"]
        for r in results:
            L.append(f"| {r['rank']} | `{r['chunk_id']}` | {r['retrieval_score']} | "
                     f"{r['citation'][:70]} |")
    L.append("")
    return L


def main() -> int:
    bk = pipeline.backend_info()
    L: list[str] = []
    add = L.append

    add("# Vi du Retrieval - Buoi 14\n")
    add(f"- top_k = {TOP_K}, candidate_k = {CANDIDATE_K}, RRF_K = {config.RRF_K}")
    add(f"- Dense backend: `{bk['dense_backend']}` "
        f"({'NEURAL' if bk['dense_is_neural'] else 'FALLBACK - khong phai neural embedding'})")
    add(f"- Rerank backend: `{bk['rerank_backend']}` "
        f"({'NEURAL' if bk['rerank_is_neural'] else 'FALLBACK - khong phai neural cross-encoder'})\n")
    add("> Ca 4 cau hinh dung CHUNG mot corpus `data/processed/chunks_normalized.csv`.\n")

    for qtype, q, why in QUERIES:
        add("---\n")
        add(f"## [{qtype}] {q}\n")
        add(f"*{why}*\n")

        out_bm = pipeline.retrieve(q, "bm25", TOP_K)
        out_dn = pipeline.retrieve(q, "dense", TOP_K)
        out_hy = pipeline.retrieve(q, "hybrid", TOP_K, CANDIDATE_K)
        out_rr = pipeline.retrieve(q, "hybrid_rerank", TOP_K, CANDIDATE_K)

        L.extend(table(out_bm["results"], "BM25-only"))
        L.extend(table(out_dn["results"], "Dense-only"))
        L.extend(table(out_hy["results"], "Hybrid (RRF)"))
        L.extend(table(out_rr["results"], "Hybrid + Rerank"))

        top_bm = out_bm["results"][0]["chunk_id"] if out_bm["results"] else None
        top_dn = out_dn["results"][0]["chunk_id"] if out_dn["results"] else None
        top_hy = out_hy["results"][0]["chunk_id"] if out_hy["results"] else None
        top_rr = out_rr["results"][0]["chunk_id"] if out_rr["results"] else None
        add("**Nhan xet**\n")
        add(f"- Top-1: BM25 `{top_bm}` | Dense `{top_dn}` | Hybrid `{top_hy}` | "
            f"Hybrid+Rerank `{top_rr}`")
        add(f"- BM25 va Dense {'CHON KHAC NHAU' if top_bm != top_dn else 'chon giong nhau'} "
            f"o vi tri #1.")
        moved = [r for r in out_rr["results"] if r.get("hybrid_rank") != r["rank"]]
        add(f"- Reranking doi cho **{len(moved)}/{len(out_rr['results'])}** ket qua trong top-{TOP_K}.")
        add("")

    add("---\n")
    add("## Doc bang the nao\n")
    add("- `bm25_rank` / `dense_rank` = `-` nghia la ung vien do **chi xuat hien o mot retriever**. "
        "Hybrid van giu lai - day chinh la ly do dung Hybrid.")
    add("- `rrf_score` tinh tu THU HANG chu khong phai tu diem tho, nen khong can chuan hoa "
        "BM25 score va cosine ve cung thang do.")
    add("- `hybrid_rank` trong bang Rerank cho biet ung vien do dung thu may TRUOC khi rerank.")

    out = config.OUTPUTS_DIR / "retrieval_examples.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"Da ghi: {out.relative_to(config.BASE_DIR)}  ({len(QUERIES)} query x 4 cau hinh)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
