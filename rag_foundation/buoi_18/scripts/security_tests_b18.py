"""
BUOI 18 - PROMPT 5: Security & Guardrail Testing.

7 bai test theo dung yeu cau cua bai hoc. Test THAT tren du lieu THAT (khong
mock), giong tinh than cua buoi_17/scripts/security_tests.py.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
sys.path.insert(0, str((BASE_DIR / "../buoi_14").resolve()))

import compliance_checker as uc3  # noqa: E402
import audit_checklist_gen as uc4  # noqa: E402
import audit_logger  # noqa: E402

OUT_MD = BASE_DIR / "outputs" / "security_test_b18_report.md"

results: list[tuple[int, str, bool, str]] = []


def record(n: int, name: str, passed: bool, detail: str) -> None:
    results.append((n, name, passed, detail))
    print(f"[{n}] {'PASS' if passed else 'FAIL'} - {name}: {detail}")


def test_1_rbac() -> None:
    """Staff khong duoc truy cap quy dinh rieng cua Risk_Manager/Admin."""
    staff_df = uc3.run_compliance_check(
        internal_document_ids=["agr_car02"], user_role="Staff", user_id="sectest01", use_llm=False,
    )
    # agr_car02 (CAR & Rui ro) chi allowed_roles ~ Admin/Risk_Manager (khong Staff)
    # -> sau RBAC filter, Staff phai KHONG thay bat ky chunk nao cua doc nay.
    passed = len(staff_df) == 0
    detail = (
        f"Staff sau loc RBAC thay {len(staff_df)} chunk thuoc agr_car02 (ky vong 0)."
        if not passed else "Staff bi chan hoan toan khoi agr_car02 (CAR & Rủi ro) sau RBAC filter — đúng."
    )
    record(1, "RBAC - Staff khong truy cap duoc du lieu rieng cua Risk_Manager/Admin", passed, detail)


def test_2_citation_integrity() -> None:
    conflicts_csv = BASE_DIR / "outputs" / "compliance_conflicts.csv"
    checklist_csv = BASE_DIR / "outputs" / "audit_checklist_results.csv"
    ok = True
    details = []
    if conflicts_csv.exists():
        with open(conflicts_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        bad = [r for r in rows if r["classification"] == "XUNG_DOT" and not (r.get("doc_a_citation") or "").strip()]
        ok = ok and not bad
        details.append(f"compliance_conflicts.csv: {len(rows)} dòng, {len(bad)} XUNG_DOT thiếu citation A")
    if checklist_csv.exists():
        with open(checklist_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        bad2 = [r for r in rows if not (r.get("source_citation") or "").strip()]
        ok = ok and not bad2
        details.append(f"audit_checklist_results.csv: {len(rows)} dòng, {len(bad2)} thiếu source_citation")
    record(2, "Citation Integrity - moi conflict/checklist item co citation hop le", ok, "; ".join(details))


def test_3_hallucination_check() -> None:
    """Kiem tra citation trong output co that su ton tai trong dataset goc."""
    import pandas as pd

    combined = pd.read_csv(BASE_DIR / os.environ.get("SOURCE_COMBINED_SECURE_CSV", "../buoi_17/data/chunks_combined_secure.csv"))
    valid_citations = set(combined["citation"].astype(str))

    ok = True
    details = []
    conflicts_csv = BASE_DIR / "outputs" / "compliance_conflicts.csv"
    if conflicts_csv.exists():
        with open(conflicts_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        fake = [r for r in rows if (r.get("doc_a_citation") or "").strip() and r["doc_a_citation"] not in valid_citations]
        fake += [r for r in rows if (r.get("doc_b_citation") or "").strip() and r["doc_b_citation"] not in valid_citations]
        ok = ok and not fake
        details.append(f"compliance_conflicts.csv: {len(fake)} citation KHÔNG khớp dataset gốc")
    checklist_csv = BASE_DIR / "outputs" / "audit_checklist_results.csv"
    if checklist_csv.exists():
        with open(checklist_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        fake2 = [r for r in rows if (r.get("source_citation") or "").strip() not in valid_citations]
        ok = ok and not fake2
        details.append(f"audit_checklist_results.csv: {len(fake2)} citation KHÔNG khớp dataset gốc")
    record(3, "Hallucination Check - moi citation xuat ra ton tai that trong dataset", ok, "; ".join(details))


def test_4_human_review_guardrail() -> None:
    ok = True
    details = []
    for fname, col in [("compliance_conflicts.csv", "review_status"), ("audit_checklist_results.csv", "review_status")]:
        path = BASE_DIR / "outputs" / fname
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        bad = [r for r in rows if r.get(col) != "NEEDS_HUMAN_REVIEW"]
        ok = ok and not bad
        details.append(f"{fname}: {len(rows)} dòng, {len(bad)} dòng SAI review_status")
    record(4, "Human Review Guardrail - moi ket qua co review_status=NEEDS_HUMAN_REVIEW", ok, "; ".join(details))


def test_5_audit_log_privacy() -> None:
    log_path = audit_logger.LOG_PATH
    if not log_path.exists():
        record(5, "Audit Log Privacy - khong luu API key/secret", False, "Chưa có audit_log.jsonl để kiểm tra.")
        return
    raw = log_path.read_text(encoding="utf-8")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    leaked_real_key = bool(api_key) and api_key in raw
    import re

    suspicious = re.search(r'"[^"]*(api[_-]?key|password|secret|token)[^"]*"\s*:\s*"(?!\[REDACTED)[^"]{6,}"',
                            raw, re.IGNORECASE)
    ok = not leaked_real_key and not suspicious
    detail = (
        f"API key thật {'BỊ LỘ' if leaked_real_key else 'không xuất hiện'} trong log; "
        f"pattern secret khả nghi chưa redact: {'CÓ' if suspicious else 'không có'}."
    )
    record(5, "Audit Log Privacy - khong luu API key/secret, da redact", ok, detail)


def test_6_unknown_domain() -> None:
    items = uc4.generate_checklist("Miền không tồn tại XYZ123", "Đơn vị test", user_role="Admin", user_id="sectest06")
    ok = items == []
    detail = (
        "Domain không có dữ liệu -> trả về danh sách rỗng, KHÔNG bịa checklist."
        if ok else f"LỖI: hệ thống vẫn sinh {len(items)} mục cho domain không tồn tại."
    )
    record(6, "Unknown Domain Test - khong bia du lieu khi domain khong ton tai", ok, detail)


def test_7_file_export() -> None:
    ok = True
    details = []
    expected = {
        "compliance_conflicts.csv": [
            "conflict_id", "domain", "doc_a_id", "doc_a_citation", "doc_a_text", "doc_b_id",
            "doc_b_citation", "doc_b_text", "conflict_type", "severity", "description",
            "review_status", "timestamp", "request_id",
        ],
        "audit_checklist_results.csv": [
            "item_id", "domain", "unit_scope", "audit_question", "risk_description", "risk_level",
            "source_citation", "recommendation", "review_status",
        ],
    }
    for fname, required_cols in expected.items():
        path = BASE_DIR / "outputs" / fname
        if not path.exists():
            ok = False
            details.append(f"{fname}: KHÔNG TỒN TẠI")
            continue
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            rows = list(reader)
        missing = [c for c in required_cols if c not in header]
        ok = ok and not missing and len(rows) > 0
        details.append(f"{fname}: {len(rows)} dòng, thiếu cột: {missing if missing else 'không'}")
    record(7, "File Export Verification - CSV dung schema, mo duoc", ok, "; ".join(details))


def main() -> None:
    test_1_rbac()
    test_2_citation_integrity()
    test_3_hallucination_check()
    test_4_human_review_guardrail()
    test_5_audit_log_privacy()
    test_6_unknown_domain()
    test_7_file_export()

    lines = ["# Buổi 18 — Security & Guardrail Test Report (PROMPT 5)\n"]
    lines.append("| # | Test | Kết quả | Chi tiết |")
    lines.append("|---|---|---|---|")
    all_pass = True
    for n, name, passed, detail in results:
        all_pass = all_pass and passed
        lines.append(f"| {n} | {name} | {'✅ PASS' if passed else '❌ FAIL'} | {detail} |")
    lines.append("")
    lines.append("## Kết luận\n")
    lines.append(f"SECURITY & GUARDRAIL TESTS: {'PASS' if all_pass else 'FAIL'}")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nDa ghi {OUT_MD}")
    print(lines[-1])

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
