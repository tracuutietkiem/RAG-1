"""
BUOI 18 - PROMPT SETUP: Kiem tra moi truong va du lieu cho Buoi 18.

Tai su dung du lieu cua buoi_17/ (agribank_internal_policies.csv,
chunks_combined_secure.csv) - KHONG copy, KHONG sua - chi doc read-only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# nap .env don gian
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

REQUIRED_14_COLS = [
    "chunk_id", "document_id", "text", "source_file", "title", "so_ky_hieu",
    "loai_van_ban", "co_quan_ban_hanh", "ngay_ban_hanh", "chapter", "section",
    "article", "citation", "allowed_roles",
]


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 9)
    return ok, f"Python {sys.version.split()[0]} ({'trong venv' if sys.prefix != sys.base_prefix else 'KHONG trong venv'})"


def check_internal_csv() -> tuple[bool, list[str]]:
    lines = []
    path = BASE_DIR / os.environ.get("SOURCE_INTERNAL_POLICY_CSV", "")
    if not path.exists():
        return False, [f"KHONG TIM THAY: {path}"]
    import pandas as pd

    df = pd.read_csv(path)
    lines.append(f"So dong: {len(df)}, so cot: {len(df.columns)}")
    missing = [c for c in REQUIRED_14_COLS if c not in df.columns]
    if missing:
        lines.append(f"THIEU cot: {missing}")
    else:
        lines.append(f"Du 14 cot metadata yeu cau: {REQUIRED_14_COLS}")
    n_docs = df["document_id"].nunique()
    lines.append(f"So van ban noi bo (document_id duy nhat): {n_docs}")
    null_report = df[REQUIRED_14_COLS].isna().sum()
    non_zero_nulls = {k: int(v) for k, v in null_report.items() if v > 0}
    lines.append(f"Cot co gia tri rong: {non_zero_nulls if non_zero_nulls else 'khong co'}")
    ok = (not missing) and len(df) > 0
    return ok, lines


def check_combined_csv() -> tuple[bool, list[str]]:
    lines = []
    path = BASE_DIR / os.environ.get("SOURCE_COMBINED_SECURE_CSV", "")
    if not path.exists():
        return False, [f"KHONG TIM THAY: {path}"]
    import pandas as pd

    df = pd.read_csv(path)
    is_internal = df["document_id"].astype(str).str.startswith("agr_")
    n_internal = int(is_internal.sum())
    n_external = int((~is_internal).sum())
    lines.append(f"Tong so chunk: {len(df)} (noi bo: {n_internal}, phap ly ben ngoai: {n_external})")
    lines.append(f"Phan bo loai_van_ban: {df['loai_van_ban'].value_counts().to_dict()}")
    ok = len(df) > 0 and n_internal > 0 and n_external > 0
    return ok, lines


def check_dirs() -> tuple[bool, list[str]]:
    lines = []
    ok = True
    for d in ("scripts", "outputs", "data", "config"):
        p = BASE_DIR / d
        exists = p.exists()
        ok = ok and True  # thu muc data/config khong bat buoc co file rieng (dung chung buoi_17)
        lines.append(f"{d}/: {'co san' if exists else 'chua co, se tao'}")
        p.mkdir(parents=True, exist_ok=True)
    return True, lines


def check_env_keys() -> tuple[bool, list[str]]:
    lines = []
    gemini = os.environ.get("GEMINI_API_KEY", "").strip()
    llm = os.environ.get("LLM_API_KEY", "").strip()
    has_key = bool(gemini or llm)
    lines.append(f"GEMINI_API_KEY: {'da dien (' + str(len(gemini)) + ' ky tu)' if gemini else 'RONG'}")
    lines.append(f"LLM_API_KEY: {'da dien (' + str(len(llm)) + ' ky tu)' if llm else 'RONG'}")
    lines.append(f"LLM_MODEL: {os.environ.get('LLM_MODEL', '(mac dinh gemini-3.6-flash)')}")
    if has_key:
        lines.append("=> Co API key: UC3/UC4 se dung LLM khi co the ket noi mang tu moi truong chay.")
    else:
        lines.append("=> KHONG co API key: UC3/UC4 se chay o che do rule-based / trich xuat (khong goi LLM).")
    return True, lines  # khong bat buoc phai co key de he thong READY (co fallback an toan)


def check_buoi17_reuse() -> tuple[bool, list[str]]:
    lines = []
    b17 = BASE_DIR / "../buoi_17"
    audit_logger = b17 / "scripts" / "audit_logger.py"
    adapter = b17 / "scripts" / "secure_retrieval_adapter.py"
    ok = audit_logger.exists() and adapter.exists()
    lines.append(f"buoi_17/scripts/audit_logger.py: {'tim thay, se reuse' if audit_logger.exists() else 'THIEU'}")
    lines.append(f"buoi_17/scripts/secure_retrieval_adapter.py: {'tim thay' if adapter.exists() else 'THIEU'}")
    b14 = BASE_DIR / "../buoi_14"
    bm25 = b14 / "src" / "bm25_retriever.py"
    roles = b14 / "roles.json"
    ok = ok and bm25.exists() and roles.exists()
    lines.append(f"buoi_14/src/bm25_retriever.py (tokenize dung chung): {'tim thay' if bm25.exists() else 'THIEU'}")
    lines.append(f"buoi_14/roles.json (single source of truth RBAC): {'tim thay' if roles.exists() else 'THIEU'}")
    return ok, lines


def main() -> None:
    report = ["# Buổi 18 — Setup & Data Check Report (PROMPT SETUP)\n"]

    py_ok, py_line = check_python()
    report.append(f"## 1. Python / venv\n\n- {py_line}\n")

    dirs_ok, dirs_lines = check_dirs()
    report.append("## 2. Thư mục dự án\n\n" + "\n".join(f"- {l}" for l in dirs_lines) + "\n")

    reuse_ok, reuse_lines = check_buoi17_reuse()
    report.append("## 3. Tái sử dụng buoi_17/ và buoi_14/\n\n" + "\n".join(f"- {l}" for l in reuse_lines) + "\n")

    try:
        internal_ok, internal_lines = check_internal_csv()
    except Exception as exc:  # noqa: BLE001
        internal_ok, internal_lines = False, [f"LOI: {type(exc).__name__}: {exc}"]
    report.append("## 4. `agribank_internal_policies.csv` (14 cột metadata)\n\n" + "\n".join(f"- {l}" for l in internal_lines) + "\n")

    try:
        combined_ok, combined_lines = check_combined_csv()
    except Exception as exc:  # noqa: BLE001
        combined_ok, combined_lines = False, [f"LOI: {type(exc).__name__}: {exc}"]
    report.append("## 5. `chunks_combined_secure.csv`\n\n" + "\n".join(f"- {l}" for l in combined_lines) + "\n")

    env_ok, env_lines = check_env_keys()
    report.append("## 6. Cấu hình `.env` (GEMINI_API_KEY / LLM_API_KEY)\n\n" + "\n".join(f"- {l}" for l in env_lines) + "\n")

    env_ready = py_ok and dirs_ok and reuse_ok
    report.append("## Kết luận\n")
    report.append(f"ENVIRONMENT READY: {'YES' if env_ready else 'NO'}")
    report.append(f"INTERNAL DATA READY: {'YES' if internal_ok else 'NO'}")
    report.append(f"COMBINED DATA READY: {'YES' if combined_ok else 'NO'}")

    out_path = BASE_DIR / "outputs" / "b18_setup_report.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Da ghi {out_path}")
    print("\n".join(report[-3:]))

    if not (env_ready and internal_ok and combined_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
