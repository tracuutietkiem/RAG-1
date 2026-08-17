"""
PROMPT 7 - Ham retrieval THONG NHAT cho ca CLI, evaluation va Streamlit.

    retrieve(question, method, top_k, candidate_k)

method: bm25 | dense | hybrid | hybrid_rerank

Moi ket qua luon co: rank, chunk_id, document_id, text, score, citation, retrieval_method.
Streamlit KHONG duoc viet lai pipeline rieng - phai goi ham nay.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import bm25_retriever, dense_retriever, hybrid_retriever, reranker  # noqa: E402

METHODS = ("bm25", "dense", "hybrid", "hybrid_rerank")


def dense_info() -> dict:
    """Thong tin backend Dense. Goi rieng de KHONG ep tai model reranker
    (~2,27 GB) khi nguoi dung chua chon che do can toi no."""
    d = dense_retriever.get_retriever()
    return {
        "dense_backend": d.backend_name,
        "dense_is_neural": d.is_neural,
        "dense_detail": d.backend_detail,
    }


def rerank_info() -> dict:
    """Thong tin backend Rerank. Lan goi dau co the phai tai model."""
    r = reranker.get_reranker()
    return {
        "rerank_backend": r.backend_name,
        "rerank_is_neural": r.is_neural,
        "rerank_detail": r.backend_detail,
    }


def backend_info() -> dict:
    """Thong tin trung thuc ve CA HAI backend (dung cho cac bao cao)."""
    return {**dense_info(), **rerank_info()}


def retrieve(
    question: str,
    method: str = "hybrid_rerank",
    top_k: int = None,
    candidate_k: int = None,
) -> dict:
    """
    Tra ve dict:
        results        : list ket qua cuoi cung (da cat top_k)
        before_rerank  : list candidate hybrid truoc khi rerank (chi voi hybrid_rerank)
        method, backend
    """
    method = (method or "hybrid_rerank").strip().lower()
    if method not in METHODS:
        raise ValueError(f"method phai thuoc {METHODS}, nhan duoc {method!r}")
    top_k = top_k or config.FINAL_TOP_K
    candidate_k = candidate_k or config.CANDIDATE_K

    out = {"method": method, "results": [], "before_rerank": [],
           "backend": dict(dense_info())}
    if method == "hybrid_rerank":
        out["backend"].update(rerank_info())

    if method == "bm25":
        out["results"] = bm25_retriever.get_retriever().search(question, top_k)
    elif method == "dense":
        out["results"] = dense_retriever.get_retriever().search(question, top_k)
    elif method == "hybrid":
        out["results"] = hybrid_retriever.get_retriever().search(
            question, top_k=top_k, candidate_k=candidate_k
        )
    else:  # hybrid_rerank
        cands = hybrid_retriever.get_retriever().candidates(question, candidate_k=candidate_k)
        out["before_rerank"] = cands
        out["results"] = reranker.get_reranker().rerank(question, cands, top_k=top_k)

    for r in out["results"]:
        r.setdefault("score", r.get("retrieval_score"))
    return out
