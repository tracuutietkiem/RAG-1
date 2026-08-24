"""
BUOI 17 - PROMPT 2: Secure Retrieval Adapter.

KHONG viet retriever moi. Adapter nay CHI goi lai
`buoi_14/src/secure_retriever.secure_search()` va chuan hoa ket qua thanh mot
schema on dinh de cac module khac cua Buoi 17 (internal_lookup, audit_logger,
app.py) dung chung, khong phai biet chi tiet noi bo cua buoi_14.

Truong chuan hoa: rank, chunk_id, document_id, title, article, citation,
allowed_roles, access_decision, retrieval_method.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
sys.path.insert(0, str(BUOI14_DIR))

import importlib  # noqa: E402

_secure_retriever = importlib.import_module("src.secure_retriever")
_config14 = importlib.import_module("config")

METHODS = _secure_retriever.METHODS


def normalize_hit(hit: dict, user_roles: list[str]) -> dict:
    allowed = hit.get("allowed_roles") or []
    granted = bool(set(user_roles) & set(allowed))
    return {
        "rank": hit.get("rank"),
        "chunk_id": hit.get("chunk_id", ""),
        "document_id": hit.get("document_id", ""),
        "title": hit.get("so_ky_hieu", "") or hit.get("document_id", ""),
        "article": hit.get("article", ""),
        "citation": hit.get("citation", ""),
        "allowed_roles": allowed,
        "access_decision": "GRANTED" if granted else "DENIED",
        "retrieval_method": hit.get("retrieval_method", ""),
        "score": hit.get("score", hit.get("retrieval_score")),
        "text": hit.get("text", ""),
    }


def secure_search(
    question: str,
    user_roles: list[str],
    method: str = "hybrid_rerank",
    top_k: int | None = None,
    candidate_k: int | None = None,
) -> dict:
    """Goi thang SecureRetriever cua buoi_14, chuan hoa output."""
    raw = _secure_retriever.secure_search(
        question, user_roles, method=method, top_k=top_k, candidate_k=candidate_k
    )
    normalized_results = [normalize_hit(h, raw["user_roles"]) for h in raw["results"]]
    return {
        "question": question,
        "method": raw["method"],
        "user_roles": raw["user_roles"],
        "results": normalized_results,
        "n_total_chunks": raw["n_total_chunks"],
        "n_visible_chunks": raw["n_visible_chunks"],
        "n_hidden_chunks": raw["n_hidden_chunks"],
        "n_candidates_rejected_by_rbac": raw["n_total_chunks"] - raw["n_visible_chunks"],
    }


def validate_roles(roles) -> list[str]:
    """Reuse thang validate_roles cua buoi_14 (single source of truth roles.json)."""
    return _config14.validate_roles(roles)


if __name__ == "__main__":
    # smoke test nhanh khi chay truc tiep file nay
    out = secure_search("Điều kiện cấp tín dụng là gì?", ["Staff"], method="hybrid", top_k=3)
    import json

    print(json.dumps(out, ensure_ascii=False, indent=2)[:1500])
