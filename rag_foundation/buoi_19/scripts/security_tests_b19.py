"""
BUOI 19 - PROMPT 5: Security & Local Guardrail Testing.

6 hang muc theo dung yeu cau cua bai. Test THAT tren du lieu THAT (khong
mock nghiep vu) - chi mock/chan mang o tang HTTP client de kiem chung
"khong goi ra Internet", giong tinh than buoi_17/buoi_18/scripts/security_tests*.py.

QUAN TRONG ve gioi han sandbox build (xem README.md): moi truong build nay
KHONG the cai Ollama that (ollama.com/Docker Hub bi chan mang o tang ha
tang). Vi vay muc #6 (Local Model Resilience) duoc kiem chung bang cach mo
phong "khong co Internet/cloud" (chan _call_gemini) va xac nhan engine VAN
tra ve ket qua hop le qua fallback rule-based/extractive - dung dung tinh
than "khong bao gio bia, luon fail an toan" xuyen suot 3 buoi. Tren may co
Ollama that + rut day mang that, hanh vi se giong het (fallback duoc thay
bang cau tra loi that cua Qwen3:0.6b vi Ollama van chay 100% local).
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
sys.path.insert(0, str((BASE_DIR / "../buoi_14").resolve()))

import compliance_checker as uc3  # noqa: E402
import audit_checklist_gen as uc4  # noqa: E402
import audit_logger  # noqa: E402
import llm_provider  # noqa: E402

OUT_MD = BASE_DIR / "outputs" / "security_test_b19_report.md"

results: list[tuple[int, str, bool, str]] = []


def record(n: int, name: str, passed: bool, detail: str) -> None:
    results.append((n, name, passed, detail))
    print(f"[{n}] {'PASS' if passed else 'FAIL'} - {name}: {detail}")


def test_1_offline_privacy() -> None:
    """LLM_PROVIDER=ollama -> (a) OLLAMA_BASE_URL phai la dia chi noi bo
    (loopback/localhost/ten service Docker noi bo, KHONG phai domain cong
    khai tren Internet), (b) duong goi Gemini/cloud (_call_gemini) KHONG bao
    gio duoc thuc thi trong toan bo pipeline UC3 khi provider=ollama."""
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    host = urlparse(base_url).hostname or ""

    # Dia chi noi bo hop le: loopback, ten host Docker Compose noi bo (khong
    # co dau cham domain cong khai vd .com/.vn), hoac mang rieng 172.x/10.x/192.168.x
    is_local = (
        host in ("localhost", "127.0.0.1", "::1", "ollama")
        or re.match(r"^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)", host) is not None
    )

    gemini_called = {"flag": False}
    orig_call_gemini = llm_provider._call_gemini

    def _raise_if_called(*args, **kwargs):  # noqa: ANN001, ANN002
        gemini_called["flag"] = True
        return orig_call_gemini(*args, **kwargs)

    llm_provider._call_gemini = _raise_if_called
    try:
        uc3.run_compliance_check(
            internal_document_ids=["agr_car02"], user_role="Admin", user_id="sectest01_b19", use_llm=True,
        )
    finally:
        llm_provider._call_gemini = orig_call_gemini

    passed = provider != "ollama" or (is_local and not gemini_called["flag"])
    detail = (
        f"LLM_PROVIDER={provider}, OLLAMA_BASE_URL={base_url} (host='{host}', is_local={is_local}), "
        f"_call_gemini đã bị gọi trong pipeline: {gemini_called['flag']} "
        "(False là đúng khi provider=ollama — không có đường nào rời khỏi mạng cục bộ)."
    )
    record(1, "Local Offline Privacy Check - khong goi ra Internet khi LLM_PROVIDER=ollama", passed, detail)


def test_2_rbac() -> None:
    staff_df = uc3.run_compliance_check(
        internal_document_ids=["agr_car02"], user_role="Staff", user_id="sectest02_b19", use_llm=False,
    )
    passed = len(staff_df) == 0
    detail = (
        f"Staff sau lọc RBAC thấy {len(staff_df)} chunk thuộc agr_car02 (kỳ vọng 0)."
        if not passed else "Staff bị chặn hoàn toàn khỏi agr_car02 (CAR & Rủi ro) sau RBAC filter — đúng."
    )
    record(2, "RBAC Enforcement - Staff bi chan 100% du lieu bao mat rui ro", passed, detail)


def test_3_citation_integrity() -> None:
    conflicts_csv = BASE_DIR / "outputs" / "compliance_conflicts.csv"
    checklist_csv = BASE_DIR / "outputs" / "audit_checklist_results.csv"
    combined_csv = BASE_DIR / os.environ["SOURCE_COMBINED_SECURE_CSV"]
    import pandas as pd
    valid_citations = set(pd.read_csv(combined_csv)["citation"].astype(str))

    ok = True
    details = []
    if conflicts_csv.exists():
        with open(conflicts_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        bad = [r for r in rows if r["classification"] == "XUNG_DOT" and not (r.get("doc_a_citation") or "").strip()]
        fake = [r for r in rows if (r.get("doc_a_citation") or "").strip() and r["doc_a_citation"] not in valid_citations]
        ok = ok and not bad and not fake
        details.append(f"compliance_conflicts.csv: {len(rows)} dòng, {len(bad)} XUNG_DOT thiếu citation, {len(fake)} citation không khớp dataset thật")
    if checklist_csv.exists():
        with open(checklist_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        bad2 = [r for r in rows if not (r.get("source_citation") or "").strip()]
        fake2 = [r for r in rows if (r.get("source_citation") or "").strip() not in valid_citations]
        ok = ok and not bad2 and not fake2
        details.append(f"audit_checklist_results.csv: {len(rows)} dòng, {len(bad2)} thiếu citation, {len(fake2)} citation không khớp dataset thật")
    record(3, "Citation Integrity - moi ket qua tu Qwen3:0.6b/Gemini co trich dan Dieu/Khoan hop le", ok, "; ".join(details))


def test_4_human_review_guardrail() -> None:
    ok = True
    details = []
    for fname in ("compliance_conflicts.csv", "audit_checklist_results.csv"):
        path = BASE_DIR / "outputs" / fname
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        bad = [r for r in rows if r.get("review_status") != "NEEDS_HUMAN_REVIEW"]
        ok = ok and not bad
        details.append(f"{fname}: {len(rows)} dòng, {len(bad)} dòng SAI review_status")
    record(4, "Human Review Guardrail - 100% ket qua co review_status=NEEDS_HUMAN_REVIEW", ok, "; ".join(details))


def test_5_audit_log_privacy() -> None:
    log_path = audit_logger.LOG_PATH
    if not log_path.exists():
        record(5, "Audit Log Privacy - khong lo API key/secret", False, "Chưa có audit_log.jsonl để kiểm tra.")
        return
    raw = log_path.read_text(encoding="utf-8")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    leaked_real_key = bool(api_key) and api_key in raw
    suspicious = re.search(r'"[^"]*(api[_-]?key|password|secret|token)[^"]*"\s*:\s*"(?!\[REDACTED)[^"]{6,}"',
                            raw, re.IGNORECASE)
    ok = not leaked_real_key and not suspicious
    detail = (
        f"API key thật {'BỊ LỘ' if leaked_real_key else 'không xuất hiện'} trong log; "
        f"pattern secret khả nghi chưa redact: {'CÓ' if suspicious else 'không có'}."
    )
    record(5, "Audit Log Privacy - khong lo API key/secret trong log", ok, detail)


def test_6_local_model_resilience() -> None:
    """Mo phong 'mat Internet/cloud hoan toan' bang cach chan duong goi
    Gemini (_call_gemini luon raise) va xac nhan UC3+UC4 VAN tra ve ket qua
    hop le (qua Ollama that neu dang chay, hoac fallback rule-based/extractive
    an toan neu Ollama cung khong san sang) - KHONG crash, KHONG bia, van giu
    NEEDS_HUMAN_REVIEW. Day la bang chung truc tiep cho 'Demo Ngat Ket Noi
    Internet' cuoi buoi: he thong khong phu thuoc bat ky duong truyen ra
    ngoai nao de tiep tuc hoat dong khi LLM_PROVIDER=ollama."""
    def _blocked_gemini(*args, **kwargs):  # noqa: ANN001, ANN002
        raise RuntimeError("[TEST] Internet/cloud bi chan hoan toan (mo phong rut day mang).")

    orig_call_gemini = llm_provider._call_gemini
    llm_provider._call_gemini = _blocked_gemini
    try:
        df = uc3.run_compliance_check(
            internal_document_ids=["agr_at01"], user_role="Admin", user_id="sectest06_b19", use_llm=True,
        )
        uc3_ok = len(df) > 0 and (df["review_status"] == "NEEDS_HUMAN_REVIEW").all()

        items = uc4.generate_checklist("An toàn kho quỹ & Vận chuyển tiền", "Chi nhánh loại 1",
                                        user_role="Admin", user_id="sectest06_b19")
        uc4_ok = len(items) > 0 and all(it["review_status"] == "NEEDS_HUMAN_REVIEW" for it in items)
        passed = uc3_ok and uc4_ok
        detail = (
            f"UC3: {len(df)} cặp, NEEDS_HUMAN_REVIEW={'đủ' if uc3_ok else 'THIẾU'}; "
            f"UC4: {len(items)} mục checklist, NEEDS_HUMAN_REVIEW={'đủ' if uc4_ok else 'THIẾU'} "
            "— cả hai vẫn phản hồi bình thường dù đường Internet/cloud bị chặn hoàn toàn."
        )
    except Exception as exc:  # noqa: BLE001
        passed = False
        detail = f"LỖI: hệ thống CRASH khi mất Internet/cloud thay vì fallback an toàn: {type(exc).__name__}: {exc}"
    finally:
        llm_provider._call_gemini = orig_call_gemini

    record(6, "Local Model Resilience - he thong van phan hoi binh thuong khi mat Internet/cloud", passed, detail)


def main() -> None:
    test_1_offline_privacy()
    test_2_rbac()
    test_3_citation_integrity()
    test_4_human_review_guardrail()
    test_5_audit_log_privacy()
    test_6_local_model_resilience()

    lines = ["# Buổi 19 — Security & Local Guardrail Test Report (PROMPT 5)\n"]
    lines.append(f"LLM_PROVIDER lúc chạy test: `{os.environ.get('LLM_PROVIDER', 'ollama')}`\n")
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
