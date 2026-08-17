#!/usr/bin/env python3
"""
BUOI 15 - PROMPT 3 (demo CLI): Secure Retrieval Pipeline.

    python scripts/secure_search_demo.py --query "..." --roles Guest --method hybrid_rerank
    python scripts/secure_search_demo.py --query "..." --roles HR,Staff --method bm25 --top-k 5

--roles nhan danh sach vai tro cach nhau boi dau phay, phai thuoc roles.json
(xem config.ALL_ROLES) - go sai se bao loi ro rang thay vi am tham chay sai.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import secure_retriever  # noqa: E402


def _log_error(exc: BaseException, context: str) -> Path:
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = config.OUTPUTS_DIR / f"error_secure_search_demo_{ts}.txt"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().isoformat()}] Loi trong: {context}\n")
        fh.write(f"{type(exc).__name__}: {exc}\n\n")
        fh.write(traceback.format_exc())
    return log_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Demo CLI tim kiem co kiem soat quyen truy cap (RBAC).")
    ap.add_argument("--query", required=True)
    ap.add_argument("--roles", required=True,
                     help=f"Danh sach vai tro cach nhau boi dau phay. Hop le: {config.ALL_ROLES}")
    ap.add_argument("--method", default="hybrid_rerank", choices=list(secure_retriever.METHODS))
    ap.add_argument("--top-k", type=int, default=config.FINAL_TOP_K)
    ap.add_argument("--candidate-k", type=int, default=config.CANDIDATE_K)
    args = ap.parse_args()

    user_roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    try:
        config.validate_roles(user_roles)
    except ValueError as exc:
        print(f"[LOI] {exc}")
        return 2

    out = secure_retriever.secure_search(
        args.query, user_roles, method=args.method,
        top_k=args.top_k, candidate_k=args.candidate_k,
    )

    print()
    print("=" * 90)
    print(f"QUERY      : {args.query}")
    print(f"USER ROLES : {out['user_roles']}")
    print(f"METHOD     : {args.method}   (top_k={args.top_k}, candidate_k={args.candidate_k})")
    print(f"Pham vi thay: {out['n_visible_chunks']}/{out['n_total_chunks']} chunk "
          f"(da loc bo {out['n_hidden_chunks']} chunk do khong du quyen)")
    print("=" * 90)

    if not out["results"]:
        print("\n(Khong co ket qua nao trong pham vi quyen truy cap hien tai.)")

    for r in out["results"]:
        print()
        print(f"#{r['rank']}  {r['chunk_id']}")
        print(f"    document_id      : {r['document_id']}  ({r.get('so_ky_hieu', '')})")
        print(f"    allowed_roles    : {r.get('allowed_roles')}")
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

    # ------------------------------------------------------------ GRAPH HINTS
    print()
    print("=" * 90)
    print("GRAPH HINTS (da loc theo quyen)")
    print("=" * 90)
    hints = secure_retriever.secure_graph_hints(out["results"], out["user_roles"])
    if not hints["available"]:
        print(f"  [!] {hints['message']}")
        print("      Van liet ke document_id / chunk_id de buoi Graph RAG sau dung tiep:")
    for d in hints["documents"]:
        print(f"  - Van ban: {d['so_ky_hieu']}")
        print(f"      chunk_id: {', '.join(d['chunk_ids'])}")
        if d["relations"]:
            for rel in d["relations"]:
                print(f"      {rel['type']} -> {rel['target']} (confidence={rel['confidence']})")
        elif hints["available"]:
            print("      (khong co quan he truc tiep toi van ban khac trong pham vi quyen)")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        log_path = _log_error(exc, context="scripts/secure_search_demo.py")
        print(f"\n[LOI] {type(exc).__name__}: {exc}")
        print(f"[LOI] Da ghi log chi tiet vao: {log_path}")
        sys.exit(1)
