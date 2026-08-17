#!/usr/bin/env python3
"""
PROMPT 2 - Baseline BM25-only va Dense-only.

Hai retriever dung CUNG mot corpus: data/processed/chunks_normalized.csv

    python scripts/baseline_retrieval.py --query "..." --top-k 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import bm25_retriever, dense_retriever  # noqa: E402


def print_results(title: str, results: list[dict], extra: str = "") -> None:
    print("=" * 78)
    print(title + (f"   [{extra}]" if extra else ""))
    print("=" * 78)
    if not results:
        print("  (khong co ket qua)")
        print()
        return
    for r in results:
        print(f"  #{r['rank']}  score={r['retrieval_score']:<12} chunk={r['chunk_id']}")
        print(f"      document_id : {r['document_id']}")
        print(f"      citation    : {r['citation']}")
        snippet = " ".join(r["text"].split())[:220]
        print(f"      text        : {snippet}...")
        print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--top-k", type=int, default=config.FINAL_TOP_K)
    args = ap.parse_args()

    print(f"\nQUERY: {args.query!r}\n")

    bm = bm25_retriever.get_retriever()
    print_results("BM25 RESULTS", bm.search(args.query, args.top_k))

    dn = dense_retriever.get_retriever()
    tag = f"backend={dn.backend_name}"
    if not dn.is_neural:
        tag += " (FALLBACK - khong phai neural embedding)"
    print_results("DENSE RESULTS", dn.search(args.query, args.top_k), extra=tag)
    print(f"Dense backend detail: {dn.backend_detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
