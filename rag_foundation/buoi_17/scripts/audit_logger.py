"""
BUOI 17 - PROMPT 3: Audit Trail.

Ghi lai MOI request truy van (tra cuu noi bo, compliance gap...) thanh 1 dong
JSON trong outputs/audit_log.jsonl (append-only). KHONG BAO GIO ghi password,
API key, secret - chi ghi metadata nghiep vu.

Dung:
    from audit_logger import log_event
    log_event(user_id="demo01", user_role="Staff", action="internal_lookup",
              query="...", retrieval_method="secure_hybrid_rerank",
              retrieved_document_ids=[...], retrieved_chunk_ids=[...],
              citation_ids=[...], n_rejected_by_rbac=5, status="SUCCESS")
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = BASE_DIR / "outputs" / "audit_log.jsonl"
_lock = Lock()

# Cac pattern KHONG duoc phep xuat hien trong log, phong truong hop mot truong
# nao do vo tinh chua secret (defense-in-depth, dung regex tho de chan som).
_SECRET_KEY_PATTERNS = re.compile(
    r"(api[_-]?key|password|secret|token|bearer\s)", re.IGNORECASE
)


def _redact(value):
    """Duyet de-quy, thay the moi chuoi trong nghi ngo la secret bang [REDACTED]."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _SECRET_KEY_PATTERNS.search(str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str) and _SECRET_KEY_PATTERNS.search(value):
        return "[REDACTED-SUSPECTED-SECRET]"
    return value


def log_event(
    *,
    user_id: str,
    user_role,
    action: str,
    query: str,
    retrieval_method: str = "",
    retrieved_document_ids: list | None = None,
    retrieved_chunk_ids: list | None = None,
    citation_ids: list | None = None,
    n_rejected_by_rbac: int = 0,
    status: str,
    extra: dict | None = None,
) -> dict:
    """Ghi 1 audit event. status: SUCCESS | DENIED | ERROR."""
    assert status in ("SUCCESS", "DENIED", "ERROR"), f"status khong hop le: {status}"

    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4()),
        "user_id_demo": user_id,
        "user_role": user_role if isinstance(user_role, list) else [user_role],
        "action": action,
        "query": query,
        "retrieval_method": retrieval_method,
        "retrieved_document_ids": retrieved_document_ids or [],
        "retrieved_chunk_ids": retrieved_chunk_ids or [],
        "citation_ids": citation_ids or [],
        "n_candidates_rejected_by_rbac": n_rejected_by_rbac,
        "status": status,
    }
    if extra:
        event["extra"] = _redact(extra)

    event = _redact(event)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_events(limit: int | None = None) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH, encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    return events[-limit:] if limit else events


if __name__ == "__main__":
    # 3 request demo bat buoc: 1) allowed  2) denied  3) binh thuong
    import sys

    sys.path.insert(0, str(BASE_DIR / "scripts"))
    import secure_retrieval_adapter as adapter

    print("== Demo 1: allowed (Staff, cau hoi tin dung) ==")
    q1 = "Điều kiện cấp tín dụng là gì?"
    out1 = adapter.secure_search(q1, ["Staff"], method="hybrid", top_k=3)
    ev1 = log_event(
        user_id="demo01", user_role="Staff", action="internal_lookup", query=q1,
        retrieval_method=out1["method"],
        retrieved_document_ids=[r["document_id"] for r in out1["results"]],
        retrieved_chunk_ids=[r["chunk_id"] for r in out1["results"]],
        citation_ids=[r["citation"] for r in out1["results"]],
        n_rejected_by_rbac=out1["n_candidates_rejected_by_rbac"],
        status="SUCCESS",
    )
    print(json.dumps(ev1, ensure_ascii=False, indent=2))

    print("\n== Demo 2: denied (unknown role) ==")
    try:
        adapter.validate_roles(["KHONG_TON_TAI"])
        ev2_status = "SUCCESS"
    except ValueError as exc:
        ev2 = log_event(
            user_id="demo02", user_role="KHONG_TON_TAI", action="internal_lookup",
            query="Điều kiện cấp tín dụng là gì?", status="DENIED",
            extra={"reason": str(exc)},
        )
        print(json.dumps(ev2, ensure_ascii=False, indent=2))

    print("\n== Demo 3: binh thuong (Guest, cau hoi chung) ==")
    q3 = "Quy định chung về hoạt động ngân hàng là gì?"
    out3 = adapter.secure_search(q3, ["Guest"], method="hybrid", top_k=3)
    ev3 = log_event(
        user_id="demo03", user_role="Guest", action="internal_lookup", query=q3,
        retrieval_method=out3["method"],
        retrieved_document_ids=[r["document_id"] for r in out3["results"]],
        retrieved_chunk_ids=[r["chunk_id"] for r in out3["results"]],
        citation_ids=[r["citation"] for r in out3["results"]],
        n_rejected_by_rbac=out3["n_candidates_rejected_by_rbac"],
        status="SUCCESS",
    )
    print(json.dumps(ev3, ensure_ascii=False, indent=2))

    print(f"\nTong so audit event da ghi: {len(read_events())}")
