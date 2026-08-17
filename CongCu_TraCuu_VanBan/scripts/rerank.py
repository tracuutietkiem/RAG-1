#!/usr/bin/env python3
"""
PROMPT 4 - Hybrid + Reranking, in BEFORE / AFTER de thay thu hang doi.

    python scripts/rerank.py --query "..." --candidate-k 20 --top-k 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import pipeline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--top-k", type=int, default=config.FINAL_TOP_K)
    ap.add_argument("--candidate-k", type=int, default=config.CANDIDATE_K)
    args = ap.parse_args()

    out = pipeline.retrieve(
        args.query, method="hybrid_rerank",
        top_k=args.top_k, candidate_k=args.candidate_k,
    )
    bk = out["backend"]

    print(f"\nQUERY: {args.query!r}")
    print(f"candidate_k={args.candidate_k}  top_k={args.top_k}")
    print(f"Reranker backend: {bk['rerank_backend']} "
          f"({'NEURAL' if bk['rerank_is_neural'] else 'FALLBACK - khong phai neural reranker'})")
    print(f"  -> {bk['rerank_detail']}\n")

    before = out["before_rerank"][: max(args.top_k, 10)]
    after = out["results"]

    print("BEFORE RERANK (thu tu Hybrid/RRF)")
    print("-" * 96)
    for r in before:
        print(f"  {r['final_rank']:>2}. {r['chunk_id']:<22} rrf={r['rrf_score']:.6f}  "
              f"{r['citation'][:48]}")
    print()
    print("AFTER RERANK")
    print("-" * 96)
    for r in after:
        moved = r["hybrid_rank"] - r["final_rank"] if r.get("hybrid_rank") else 0
        arrow = f"(hybrid #{r['hybrid_rank']}, {'+' if moved > 0 else ''}{moved})" if moved else \
                f"(hybrid #{r['hybrid_rank']}, giu nguyen)"
        print(f"  {r['final_rank']:>2}. {r['chunk_id']:<22} rerank={r['rerank_score']:.6f}  "
              f"{arrow}")
        print(f"      {r['citation'][:80]}")
    print()

    changed = any(r.get("hybrid_rank") != r["final_rank"] for r in after)
    print(f"Thu hang co thay doi sau rerank: {'CO' if changed else 'KHONG'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
