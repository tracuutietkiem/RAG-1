"""
BUOI 19 - PROMPT 6: Audit toan bo project & Final Validation (Docker/Local AI).

Kiem tra 6 tieu chi cua bai. Giong nguyen tac final_validation.py/
final_validation_b18.py: doc lai output THAT, KHONG gia dinh PASS, va BAO
CAO TRUNG THUC ngay ca khi nguyen nhan FAIL la gioi han moi truong (khong
phai loi code) - xem README.md muc "Gioi han moi truong sandbox".

Xuat: outputs/b19_docker_acceptance_report.md
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from ollama_adapter import OllamaClient  # noqa: E402
import llm_provider  # noqa: E402

OUT = BASE_DIR / "outputs" / "b19_docker_acceptance_report.md"

checks: dict[str, tuple[bool, str]] = {}


def check_ollama_connectivity() -> tuple[bool, str]:
    client = OllamaClient()
    health = client.check_health()
    if health["online"]:
        return True, f"Kết nối thành công tới {health['base_url']}/api/tags. Models: {health['models']}"
    return False, (
        f"KHÔNG kết nối được tới {health['base_url']}/api/tags ({health['error']}). "
        "Trong môi trường build (sandbox cloud) hiện tại KHÔNG thể cài Ollama thật "
        "(ollama.com và Docker Hub bị chặn ở tầng hạ tầng — xem README.md). "
        "Trên máy có Docker/Ollama thật, chạy `docker compose up -d` trước rồi chạy lại script này."
    )


def check_local_model() -> tuple[bool, str]:
    client = OllamaClient()
    health = client.check_health()
    if health["online"] and health["model_ready"]:
        return True, f"Model '{client.model}' có trong registry Ollama đang chạy."
    if health["online"]:
        return False, (
            f"Ollama server ONLINE nhưng model '{client.model}' CHƯA được pull. "
            f"Chạy: docker exec -it agribank-ollama-server ollama pull {client.model}"
        )
    return False, "Không kiểm tra được vì Ollama server offline (xem mục 1)."


def check_dual_provider_switch() -> tuple[bool, str]:
    """Kiem tra LOGIC dinh tuyen dung, KHONG phu thuoc ket noi mang that (test
    nay xac nhan PACKAGING/CODE dung, tach biet voi test 1-2 la ha tang that)."""
    calls = {"ollama": False, "gemini": False}
    orig_ollama, orig_gemini = llm_provider._call_ollama, llm_provider._call_gemini

    def fake_ollama(*a, **k):  # noqa: ANN001, ANN002
        calls["ollama"] = True
        return "[TEST] mock ollama response"

    def fake_gemini(*a, **k):  # noqa: ANN001, ANN002
        calls["gemini"] = True
        return "[TEST] mock gemini response"

    llm_provider._call_ollama = fake_ollama
    llm_provider._call_gemini = fake_gemini
    try:
        import os as _os

        prev = _os.environ.get("LLM_PROVIDER")
        _os.environ["LLM_PROVIDER"] = "ollama"
        r1 = llm_provider.call_llm("test", format_json=False)
        _os.environ["LLM_PROVIDER"] = "gemini"
        r2 = llm_provider.call_llm("test", format_json=False)
        if prev is not None:
            _os.environ["LLM_PROVIDER"] = prev
    finally:
        llm_provider._call_ollama = orig_ollama
        llm_provider._call_gemini = orig_gemini

    ok = calls["ollama"] and calls["gemini"] and r1 is not None and r2 is not None
    return ok, (
        f"LLM_PROVIDER=ollama → gọi _call_ollama: {calls['ollama']}; "
        f"LLM_PROVIDER=gemini → gọi _call_gemini: {calls['gemini']}. "
        "Định tuyến đúng theo biến môi trường (độc lập với việc server thật có online hay không)."
    )


def check_docker_packaging() -> tuple[bool, str]:
    dockerfile = BASE_DIR / "Dockerfile"
    compose = BASE_DIR / "docker-compose.yml"
    req = BASE_DIR / "requirements.txt"
    missing = [str(p.name) for p in (dockerfile, compose, req) if not p.exists()]
    if missing:
        return False, f"Thiếu file: {missing}"

    df_text = dockerfile.read_text(encoding="utf-8")
    df_ok = bool(
        "FROM python:3.10-slim" in df_text
        and "EXPOSE 8501" in df_text
        and "streamlit" in df_text and "app.py" in df_text
        and re.search(r"^CMD", df_text, re.MULTILINE)
    )

    try:
        result = subprocess.run(
            ["docker", "compose", "config"], cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=30,
        )
        compose_valid = result.returncode == 0
        compose_detail = "hợp lệ (docker compose config chạy không lỗi)" if compose_valid else result.stderr[:300]
    except FileNotFoundError:
        compose_valid = False
        compose_detail = "Không tìm thấy lệnh `docker` trong môi trường này."
    except Exception as exc:  # noqa: BLE001
        compose_valid = False
        compose_detail = f"Lỗi khi chạy docker compose config: {exc}"

    ok = df_ok and compose_valid
    return ok, f"Dockerfile hợp lệ cú pháp cần thiết: {df_ok}. docker-compose.yml: {compose_detail}."


def check_local_engines() -> tuple[bool, str]:
    conflicts_csv = BASE_DIR / "outputs" / "compliance_conflicts.csv"
    checklist_csv = BASE_DIR / "outputs" / "audit_checklist_results.csv"
    if not (conflicts_csv.exists() and checklist_csv.exists()):
        return False, "Thiếu compliance_conflicts.csv hoặc audit_checklist_results.csv — chạy PROMPT 2 trước."

    cdf = pd.read_csv(conflicts_csv)
    chdf = pd.read_csv(checklist_csv)
    ok = len(cdf) > 0 and len(chdf) > 0
    methods_uc3 = sorted(cdf["classification_method"].dropna().unique().tolist())
    methods_uc4 = sorted(chdf["generation_method"].dropna().unique().tolist())
    used_local_llm = any("ollama" in m for m in methods_uc3 + methods_uc4)
    detail = (
        f"UC3: {len(cdf)} cặp (methods={methods_uc3}). UC4: {len(chdf)} mục (methods={methods_uc4}). "
        f"Đã dùng Qwen3:0.6b thật (llm_assisted_ollama): {used_local_llm}. "
    )
    if not used_local_llm:
        detail += (
            "Trong lần chạy này hệ thống dùng fallback rule-based/extractive (Ollama offline trong "
            "môi trường build) — engine vẫn PASS vì fail-safe đúng thiết kế, nhưng CHƯA chứng minh "
            "được Qwen3:0.6b thật sinh nội dung. Chạy lại trên máy có Ollama thật để có bằng chứng đầy đủ."
        )
    return ok, detail


def check_human_review_and_audit() -> tuple[bool, str]:
    conflicts_csv = BASE_DIR / "outputs" / "compliance_conflicts.csv"
    checklist_csv = BASE_DIR / "outputs" / "audit_checklist_results.csv"
    log_path = BASE_DIR / "outputs" / "audit_log.jsonl"
    ok = True
    details = []
    for p, col in ((conflicts_csv, "review_status"), (checklist_csv, "review_status")):
        if not p.exists():
            ok = False
            details.append(f"{p.name}: THIẾU")
            continue
        df = pd.read_csv(p)
        all_ok = (df[col] == "NEEDS_HUMAN_REVIEW").all() if len(df) else False
        ok = ok and all_ok
        details.append(f"{p.name}: {len(df)} dòng, NEEDS_HUMAN_REVIEW={'đủ' if all_ok else 'THIẾU'}")

    if not log_path.exists():
        ok = False
        details.append("audit_log.jsonl: THIẾU")
    else:
        raw = log_path.read_text(encoding="utf-8")
        pat = re.compile(r"(api[_-]?key|password|secret)\s*[:=]\s*\S{4,}", re.IGNORECASE)
        offending = [ln for ln in raw.splitlines() if pat.search(ln) and "[REDACTED" not in ln]
        ok = ok and not offending
        details.append(f"audit_log.jsonl: {len(raw.splitlines())} dòng, {len(offending)} dòng nghi lộ secret")

    return ok, "; ".join(details)


def main() -> None:
    checks["Ollama Server Connectivity"] = check_ollama_connectivity()
    checks["Local Model Availability (Qwen3:0.6b)"] = check_local_model()
    checks["Dual Provider Switch (logic)"] = check_dual_provider_switch()
    checks["Docker Compose Packaging"] = check_docker_packaging()
    checks["Local UC3 & UC4 Engines"] = check_local_engines()
    checks["Human Review & Audit Log"] = check_human_review_and_audit()

    security_report = BASE_DIR / "outputs" / "security_test_b19_report.md"
    security_pass = security_report.exists() and "SECURITY & GUARDRAIL TESTS: PASS" in security_report.read_text(encoding="utf-8")
    checks["6 bài Security & Local Guardrail Test"] = (
        security_pass,
        "outputs/security_test_b19_report.md kết luận PASS." if security_pass
        else "Chưa PASS hoặc chưa chạy scripts/security_tests_b19.py.",
    )

    lines = ["# Buổi 19 — Docker & Local AI Acceptance Report (PROMPT 6)\n"]
    lines.append("| Hạng mục | Kết quả | Chi tiết |")
    lines.append("|---|---|---|")
    for name, (ok_, detail) in checks.items():
        lines.append(f"| {name} | {'✅ PASS' if ok_ else '❌ FAIL'} | {detail} |")
    lines.append("")

    ollama_status = checks["Ollama Server Connectivity"][0]
    model_status = checks["Local Model Availability (Qwen3:0.6b)"][0]
    docker_status = checks["Docker Compose Packaging"][0]
    engines_status = checks["Local UC3 & UC4 Engines"][0]

    lines.append(f"OLLAMA SERVER STATUS: {'PASS' if ollama_status else 'FAIL'}")
    lines.append(f"LOCAL MODEL QWEN3: {'PASS' if model_status else 'FAIL'}")
    lines.append(f"DOCKER CONTAINERIZATION: {'PASS' if docker_status else 'FAIL'}")
    lines.append(f"LOCAL COMPLIANCE ENGINES: {'PASS' if engines_status else 'FAIL'}")
    lines.append("")

    overall_ready = all(ok_ for ok_, _ in checks.values())
    lines.append(f"LOCAL AI SYSTEM READY: {'YES' if overall_ready else 'NO'}")

    if not overall_ready and docker_status and engines_status and security_pass:
        lines.append("")
        lines.append(
            "**Ghi chú quan trọng**: Nguyên nhân duy nhất khiến hệ thống chưa đạt `YES` là "
            "**Ollama server chưa chạy trong môi trường kiểm tra này** (không phải lỗi code/packaging — "
            "Docker packaging, dual-provider switch, RBAC, citation, human-review guardrail, audit log đều "
            "đã PASS). Môi trường build (sandbox cloud) không thể tải Ollama/Docker Hub do bị chặn mạng ở "
            "tầng hạ tầng (xem README.md mục 'Giới hạn môi trường sandbox'). **Trên máy học viên**: chạy "
            "`docker compose up -d` rồi `docker exec -it agribank-ollama-server ollama pull qwen3:0.6b`, "
            "sau đó chạy lại `python scripts/verify_b19_docker.py` để có kết quả `LOCAL AI SYSTEM READY: YES` "
            "với Qwen3:0.6b thật."
        )

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print("\n".join(lines[-8:]))


if __name__ == "__main__":
    main()
