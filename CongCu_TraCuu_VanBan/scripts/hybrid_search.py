#!/usr/bin/env python3
"""
PROMPT 3 - Hybrid Search bang RRF.

    python scripts/hybrid_search.py --query "..." --candidate-k 20 --top-k 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import hybrid_retriever  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--top-k", type=int, default=config.FINAL_TOP_K)
    ap.add_argument("--candidate-k", type=int, default=config.CANDIDATE_K)
    args = ap.parse_args()

    hy = hybrid_retriever.get_retriever()
    results = hy.search(args.query, top_k=args.top_k, candidate_k=args.candidate_k)

    print(f"\nQUERY: {args.query!r}")
    print(f"candidate_k={args.candidate_k}  top_k={args.top_k}  "
          f"RRF_K={config.RRF_K}  dense_backend={hy.dense_backend}\n")
    print("HYBRID RESULTS")
    print("-" * 104)
    print(f"{'Rank':<5}{'Chunk':<22}{'BM25':<7}{'Dense':<7}{'RRF':<11}Citation")
    print("-" * 104)
    for r in results:
        bm = r["bm25_rank"] if r["bm25_rank"] is not None else "-"
        dn = r["dense_rank"] if r["dense_rank"] is not None else "-"
        cite = r["citation"]
        print(f"{r['final_rank']:<5}{r['chunk_id']:<22}{str(bm):<7}{str(dn):<7}"
              f"{r['rrf_score']:<11.6f}{cite[:52]}")
    print("-" * 104)
    print("Ghi chu: '-' nghia la candidate chi xuat hien o mot retriever "
          "(van duoc giu lai, dung tinh than Hybrid).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
