#!/usr/bin/env python3
"""
BUOI 15 - PROMPT 1: Phan loai bao mat va gan tag quyen truy cap (Security Tagging).

    python scripts/assign_security_tags.py

Doc  : buoi_14/data/processed/chunks_normalized.csv   (KHONG sua doi)
Ghi  : buoi_14/data/processed/chunks_secure.csv        ([NEW] + cot allowed_roles)

Logic phan loai (o muc CHUNK, khong phai ca van ban, de bam sat noi dung tung
Dieu/khoan): dua vao tu khoa xuat hien trong `text` + `title` cua chunk, doc tu
`roles.json -> classification_rules` (single source of truth, xem config.py):

    1) Khop tu khoa HR             -> allowed_roles = ["Admin", "HR"]
    2) Khop tu khoa Risk_Manager   -> allowed_roles = ["Admin", "Risk_Manager", "Staff"]
    3) Khong khop gi               -> allowed_roles = ["Admin", "HR", "Risk_Manager",
                                                        "Staff", "Guest"]  (GENERAL)

Nguyen tac uu tien "most-restrictive-wins": kiem tra HR TRUOC Risk_Manager, vi
mot chunk co the vua nhac "nguoi quan ly" (HR) vua nhac "tin dung" (Risk) - danh
gia sai theo huong LO RA it nguy hiem hon danh gia sai theo huong AN QUA rong.
"""

from __future__ import annotations

import csv
import json
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

ERROR_LOG_DIR = config.BASE_DIR / "outputs"


def _log_error(exc: BaseException, context: str) -> Path:
    """Theo quy dinh: moi loi khi chay code/xu ly file phai duoc ghi log ra
    file .txt trong thu muc outputs/ va bao ngay cho nguoi dung."""
    ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = ERROR_LOG_DIR / f"error_assign_security_tags_{ts}.txt"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().isoformat()}] Loi trong: {context}\n")
        fh.write(f"{type(exc).__name__}: {exc}\n\n")
        fh.write(traceback.format_exc())
    return log_path


def classify_chunk(text: str, title: str) -> str:
    """Tra ve 'HR' | 'RISK' | 'GENERAL' theo tu khoa (khong phan biet hoa/thuong)."""
    haystack = f"{text or ''} {title or ''}".lower()

    hr_kw = config.CLASSIFICATION_RULES.get("HR", {}).get("keywords", [])
    if any(kw.lower() in haystack for kw in hr_kw):
        return "HR"

    risk_kw = config.CLASSIFICATION_RULES.get("Risk_Manager", {}).get("keywords", [])
    if any(kw.lower() in haystack for kw in risk_kw):
        return "RISK"

    return "GENERAL"


def allowed_roles_for(category: str) -> list[str]:
    if category == "HR":
        return list(config.CLASSIFICATION_RULES.get("HR", {}).get(
            "allowed_roles", ["Admin", "HR"]))
    if category == "RISK":
        return list(config.CLASSIFICATION_RULES.get("Risk_Manager", {}).get(
            "allowed_roles", ["Admin", "Risk_Manager", "Staff"]))
    return list(config.CLASSIFICATION_RULES.get("GENERAL", {}).get(
        "allowed_roles", config.ALL_ROLES))


def run() -> None:
    src = config.CHUNKS_CSV
    dst = config.CHUNKS_SECURE_CSV

    if not src.exists():
        raise FileNotFoundError(
            f"Khong thay {src}. Chay truoc: python scripts/prepare_corpus.py"
        )

    print(f"Doc: {src}")
    with open(src, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if not rows:
        raise RuntimeError(f"{src} rong - khong co du lieu de gan tag.")

    category_counter: Counter[str] = Counter()
    role_group_counter: Counter[str] = Counter()
    samples: dict[str, dict] = {}

    out_rows = []
    n_empty_roles = 0
    for row in rows:
        category = classify_chunk(row.get("text", ""), row.get("title", ""))
        roles = allowed_roles_for(category)
        if not roles:
            n_empty_roles += 1
            roles = list(config.ALL_ROLES)  # an toan: khong bao gio de trong

        category_counter[category] += 1
        role_group_counter[",".join(roles)] += 1
        if category not in samples:
            samples[category] = {**row, "allowed_roles": roles}

        new_row = dict(row)
        new_row["allowed_roles"] = json.dumps(roles, ensure_ascii=False)
        new_row["security_category"] = category
        out_rows.append(new_row)

    out_fieldnames = fieldnames + ["allowed_roles", "security_category"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    # ---------------------------------------------------------- kiem tra
    if n_empty_roles:
        raise RuntimeError(
            f"Phat hien {n_empty_roles} dong co allowed_roles rong sau khi gan tag - "
            "dung lai de tranh rui ro bao mat (fail-closed)."
        )

    print(f"\nGhi: {dst}  ({len(out_rows)} dong)")
    print("\n=== THONG KE THEO NHOM PHAN QUYEN (allowed_roles) ===")
    for roles_str, n in role_group_counter.most_common():
        print(f"  [{roles_str}] : {n} chunk")

    print("\n=== THONG KE THEO PHAN LOAI NOI DUNG ===")
    for cat in ("HR", "RISK", "GENERAL"):
        print(f"  {cat:8s}: {category_counter.get(cat, 0)} chunk")

    print(f"\nKiem tra: 0/{len(out_rows)} dong co allowed_roles rong -> OK")

    print("\n=== 3 DONG MAU DAI DIEN 3 CAP DO BAO MAT ===")
    for cat in ("HR", "RISK", "GENERAL"):
        r = samples.get(cat)
        if not r:
            continue
        print(f"\n--- {cat} ---")
        print(f"  chunk_id      : {r.get('chunk_id')}")
        print(f"  document_id   : {r.get('document_id')}")
        print(f"  so_ky_hieu    : {r.get('so_ky_hieu')}")
        print(f"  citation      : {(r.get('citation') or '')[:100]}")
        print(f"  allowed_roles : {r.get('allowed_roles')}")
        print(f"  text (100 ky tu dau): {(r.get('text') or '')[:100]!r}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        log_path = _log_error(exc, context="scripts/assign_security_tags.py")
        print(f"\n[LOI] {type(exc).__name__}: {exc}")
        print(f"[LOI] Da ghi log chi tiet vao: {log_path}")
        sys.exit(1)
