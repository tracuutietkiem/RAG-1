#!/usr/bin/env python3
"""
PROMPT 7 - Demo retrieval thong nhat + GRAPH HINTS.

    python scripts/query_demo.py --query "..." --method hybrid_rerank --top-k 5

method: bm25 | dense | hybrid | hybrid_rerank
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import graph_hints, pipeline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--method", default="hybrid_rerank", choices=list(pipeline.METHODS))
    ap.add_argument("--top-k", type=int, default=config.FINAL_TOP_K)
    ap.add_argument("--candidate-k", type=int, default=config.CANDIDATE_K)
    args = ap.parse_args()

    out = pipeline.retrieve(
        args.query, method=args.method,
        top_k=args.top_k, candidate_k=args.candidate_k,
    )
    bk = out["backend"]

    print()
    print("=" * 86)
    print(f"QUERY   : {args.query}")
    print(f"METHOD  : {args.method}   (top_k={args.top_k}, candidate_k={args.candidate_k})")
    print(f"BACKEND : dense={bk['dense_backend']}"
          f"{'' if bk['dense_is_neural'] else ' [FALLBACK]'}"
          f" | rerank={bk['rerank_backend']}"
          f"{'' if bk['rerank_is_neural'] else ' [FALLBACK]'}")
    print("=" * 86)

    for r in out["results"]:
        print()
        print(f"#{r['rank']}  {r['chunk_id']}")
        print(f"    document_id      : {r['document_id']}  ({r.get('so_ky_hieu', '')})")
        print(f"    score            : {r.get('score', r.get('retrieval_score'))}")
        print(f"    retrieval_method : {r['retrieval_method']}")
        if r.get("bm25_rank") is not None or r.get("dense_rank") is not None:
            print(f"    bm25_rank={r.get('bm25_rank', '-')}  dense_rank={r.get('dense_rank', '-')}"
                  f"  rrf_score={r.get('rrf_score', '-')}")
        if r.get("rerank_score") is not None:
            print(f"    hybrid_rank={r.get('hybrid_rank', '-')}  "
                  f"hybrid_score={r.get('hybrid_score', '-')}  "
                  f"rerank_score={r.get('rerank_score')}")
        print(f"    citation         : {r['citation']}")
        snippet = " ".join(r["text"].split())[:300]
        print(f"    text             : {snippet}...")

    if args.method == "hybrid_rerank" and out["before_rerank"]:
        print()
        print("-" * 86)
        print("BEFORE RERANK  ->  AFTER RERANK")
        print("-" * 86)
        before = out["before_rerank"][: args.top_k]
        after = out["results"]
        for i in range(max(len(before), len(after))):
            b = before[i]["chunk_id"] if i < len(before) else ""
            a = after[i]["chunk_id"] if i < len(after) else ""
            print(f"  {i + 1}. {b:<26} ->  {a}")

    # ------------------------------------------------------------ GRAPH HINTS
    print()
    print("=" * 86)
    print("GRAPH HINTS")
    print("=" * 86)
    hints = graph_hints.graph_hints(out["results"])
    if not hints["available"]:
        print(f"  [!] {hints['message']}")
        print("      Van liet ke document_id / chunk_id de buoi Graph RAG sau dung tiep:")
    for d in hints["documents"]:
        print(f"  - Van ban: {d['so_ky_hieu']}")
        print(f"      chunk_id: {', '.join(d['chunk_ids'])}")
        if d["relations"]:
            for rel in d["relations"]:
                print(f"      {rel['type']} -> {rel['target']} "
                      f"(confidence={rel['confidence']})")
        elif hints["available"]:
            print("      (khong co quan he truc tiep toi van ban khac)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
