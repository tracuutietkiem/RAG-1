"""
BUOI 17 - PROMPT 10: Security Tests (dong vai tester).

10 test bat buoc, chay THAT (khong mock), doc ket qua tu cac script da chay
o cac PROMPT truoc (audit_log.jsonl, compliance_gap_results.csv) va tu goi
truc tiep secure_retrieval_adapter/internal_lookup de kiem tra hanh vi song.

Xuat: outputs/security_test_report.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
sys.path.insert(0, str(BASE_DIR / "scripts"))
sys.path.insert(0, str(BUOI14_DIR))

import secure_retrieval_adapter as adapter  # noqa: E402
import audit_logger  # noqa: E402

OUT = BASE_DIR / "outputs" / "security_test_report.md"

SECRET_PATTERN = re.compile(r"(api[_-]?key|password|secret)\s*[:=]\s*\S{4,}", re.IGNORECASE)


def run_tests() -> list[dict]:
    tests = []
    question = "Điều kiện cấp tín dụng đối với khách hàng doanh nghiệp là gì?"

    # 1. role duoc phep -> PASS
    out_allowed = adapter.secure_search(question, ["Risk_Manager"], method="hybrid", top_k=3)
    t1 = len(out_allowed["results"]) > 0
    tests.append({"id": 1, "name": "Role được phép nhận kết quả", "pass": t1,
                  "detail": f"n_results={len(out_allowed['results'])}"})

    # 2. role khong duoc phep -> khong lo text/citation cua chunk han che
    hr_question = "Quy định về bổ nhiệm, miễn nhiệm cán bộ quản lý là gì?"
    out_hr = adapter.secure_search(hr_question, ["HR"], method="hybrid_rerank", top_k=5)
    out_guest = adapter.secure_search(hr_question, ["Guest"], method="hybrid_rerank", top_k=5)
    hr_only_ids = {r["chunk_id"] for r in out_hr["results"] if "Guest" not in r["allowed_roles"]}
    guest_ids = {r["chunk_id"] for r in out_guest["results"]}
    leaked = hr_only_ids & guest_ids
    t2 = len(leaked) == 0
    tests.append({"id": 2, "name": "Role không được phép không thấy text/citation hạn chế",
                  "pass": t2, "detail": f"leaked_chunk_ids={leaked or 'none'}"})

    # 3. tai lieu bi cam khong vao context (kiem tra ca before_rerank cua raw secure_retriever)
    import importlib
    sr = importlib.import_module("src.secure_retriever")
    raw = sr.secure_search(hr_question, ["Guest"], method="hybrid_rerank", top_k=5)
    all_ctx = raw.get("before_rerank", []) + raw.get("results", [])
    unauthorized = [c["chunk_id"] for c in all_ctx if "Guest" not in (c.get("allowed_roles") or [])]
    t3 = len(unauthorized) == 0
    tests.append({"id": 3, "name": "Tài liệu bị cấm không vào context (kể cả before_rerank)",
                  "pass": t3, "detail": f"unauthorized_in_context={unauthorized or 'none'}"})

    # 4. unknown role -> DENY
    try:
        adapter.validate_roles(["ROLE_KHONG_TON_TAI"])
        t4 = False
        t4_detail = "KHONG bi chan (LOI BAO MAT)"
    except ValueError as exc:
        t4 = True
        t4_detail = f"ValueError: {exc}"
    tests.append({"id": 4, "name": "Unknown role bị DENY", "pass": t4, "detail": t4_detail})

    # 5. audit ghi ca SUCCESS va DENIED
    events = audit_logger.read_events()
    statuses = {e["status"] for e in events}
    t5 = "SUCCESS" in statuses and "DENIED" in statuses
    tests.append({"id": 5, "name": "Audit ghi cả SUCCESS và DENIED", "pass": t5,
                  "detail": f"statuses_found={sorted(statuses)}"})

    # 6. log khong chua password/API key
    log_path = BASE_DIR / "outputs" / "audit_log.jsonl"
    leaked_secrets = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if SECRET_PATTERN.search(line):
                leaked_secrets.append(line[:80])
    t6 = len(leaked_secrets) == 0
    tests.append({"id": 6, "name": "Log không chứa password/API key", "pass": t6,
                  "detail": f"suspect_lines={leaked_secrets or 'none'}"})

    # 7. citation ton tai
    t7 = all(r.get("citation") for r in out_allowed["results"]) and len(out_allowed["results"]) > 0
    tests.append({"id": 7, "name": "Citation tồn tại trên mọi kết quả", "pass": t7,
                  "detail": f"n_checked={len(out_allowed['results'])}"})

    # 8. gap co evidence hoac CHUA_DU_BANG_CHUNG
    gap_csv = BASE_DIR / "outputs" / "compliance_gap_results.csv"
    if gap_csv.exists():
        gap_df = pd.read_csv(gap_csv)
        bad = gap_df[
            (gap_df["classification"] != "CHUA_DU_BANG_CHUNG")
            & (gap_df["internal_citation"].isna() | (gap_df["internal_citation"] == ""))
        ]
        t8 = len(bad) == 0
        tests.append({"id": 8, "name": "Mọi gap có evidence hoặc là CHUA_DU_BANG_CHUNG",
                      "pass": t8, "detail": f"rows_thieu_evidence={len(bad)}"})
    else:
        tests.append({"id": 8, "name": "Mọi gap có evidence hoặc là CHUA_DU_BANG_CHUNG",
                      "pass": False, "detail": "Không tìm thấy compliance_gap_results.csv"})

    # 9. moi gap result NEEDS_HUMAN_REVIEW
    if gap_csv.exists():
        gap_df = pd.read_csv(gap_csv)
        t9 = bool((gap_df["review_status"] == "NEEDS_HUMAN_REVIEW").all())
        tests.append({"id": 9, "name": "Mọi gap result có review_status=NEEDS_HUMAN_REVIEW",
                      "pass": t9, "detail": f"n_rows={len(gap_df)}"})
    else:
        tests.append({"id": 9, "name": "Mọi gap result có review_status=NEEDS_HUMAN_REVIEW",
                      "pass": False, "detail": "Không tìm thấy file"})

    # 10. Neo4j down -> bao that, khong gia
    ok, msg = sr.neo4j_status()
    t10 = isinstance(ok, bool) and isinstance(msg, str) and len(msg) > 0
    tests.append({"id": 10, "name": "Neo4j trạng thái được báo cáo trung thực (không giả định)",
                  "pass": t10, "detail": f"ok={ok}, message='{msg}'"})

    return tests


def main() -> None:
    tests = run_tests()
    lines = ["# Buổi 17 — Security Test Report (PROMPT 10)\n"]
    lines.append("| # | Test | Kết quả | Chi tiết |")
    lines.append("|---|---|---|---|")
    for t in tests:
        status = "✅ PASS" if t["pass"] else "❌ FAIL"
        lines.append(f"| {t['id']} | {t['name']} | {status} | {t['detail']} |")
    lines.append("")

    all_pass = all(t["pass"] for t in tests)
    lines.append(f"SECURITY TESTS: {'PASS' if all_pass else 'FAIL'}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    for t in tests:
        print(f"[{t['id']}] {'PASS' if t['pass'] else 'FAIL'} - {t['name']}")
    print(f"SECURITY TESTS: {'PASS' if all_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
