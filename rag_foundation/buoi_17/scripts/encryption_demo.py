"""
BUOI 17 - PROMPT 4: Demo encryption at-rest (chi minh hoa, KHONG production-ready).

Dung Fernet (cryptography). Key KHONG hard-code: sinh ngau nhien moi lan chay
demo va luu vao file *.key rieng (da khai bao trong .gitignore), tach biet voi
file du lieu da ma hoa.

Chay:  python scripts/encryption_demo.py
Xuat:  outputs/encryption_demo_report.md
       outputs/audit_log_demo.enc      (ban ma hoa cua audit_log.jsonl)
       outputs/audit_log_demo.key      (key rieng - KHONG commit that len git)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "outputs" / "audit_log.jsonl"
ENC_FILE = BASE_DIR / "outputs" / "audit_log_demo.enc"
KEY_FILE = BASE_DIR / "outputs" / "audit_log_demo.key"
OUT = BASE_DIR / "outputs" / "encryption_demo_report.md"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    lines = ["# Buổi 17 — Encryption Demo Report (PROMPT 4)\n"]
    lines.append(
        "**Mục tiêu**: minh hoạ bảo vệ dữ liệu at-rest bằng mã hoá đối xứng (Fernet/AES). "
        "Đây CHỈ là demo giáo dục — KHÔNG phải giải pháp bảo mật production.\n"
    )

    if not SOURCE_FILE.exists():
        lines.append(f"**LỖI**: không tìm thấy {SOURCE_FILE} — chạy `audit_logger.py` trước.")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        print("FAIL: thiếu file nguồn")
        return

    # 1) sinh key ngau nhien, KHONG hard-code, luu rieng
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    fernet = Fernet(key)

    # 2) encrypt
    original_bytes = SOURCE_FILE.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    token = fernet.encrypt(original_bytes)
    ENC_FILE.write_bytes(token)
    encrypt_ok = ENC_FILE.exists() and ENC_FILE.stat().st_size > 0

    # 3) decrypt + so khop
    decrypted_bytes = fernet.decrypt(ENC_FILE.read_bytes())
    decrypted_hash = hashlib.sha256(decrypted_bytes).hexdigest()
    decrypt_match = decrypted_hash == original_hash

    lines.append("## Kết quả\n")
    lines.append(f"- File nguồn: `{SOURCE_FILE.relative_to(BASE_DIR)}` ({len(original_bytes)} bytes)")
    lines.append(f"- Key: sinh ngẫu nhiên bằng `Fernet.generate_key()`, lưu tại "
                 f"`{KEY_FILE.relative_to(BASE_DIR)}` (đã có trong `.gitignore`, KHÔNG hard-code trong source)")
    lines.append(f"- File mã hoá: `{ENC_FILE.relative_to(BASE_DIR)}` ({ENC_FILE.stat().st_size} bytes)")
    lines.append(f"- SHA256 gốc:    `{original_hash}`")
    lines.append(f"- SHA256 sau khi giải mã: `{decrypted_hash}`")
    lines.append(f"- Encrypt thành công: {'CÓ' if encrypt_ok else 'KHÔNG'}")
    lines.append(f"- Decrypt khớp 100% với bản gốc: {'CÓ' if decrypt_match else 'KHÔNG'}")
    lines.append("")
    lines.append("## Giới hạn (học viên PHẢI hiểu rõ)\n")
    lines.append(
        "Demo này chỉ chứng minh cơ chế mã hoá/giải mã hoạt động đúng trên một file cụ thể. "
        "Một hệ thống thật còn cần thêm: TLS cho dữ liệu truyền tải (in-transit), quản lý vòng đời "
        "khoá (key management/rotation) qua KMS/HSM chuyên dụng, sao lưu (backup) có mã hoá, và "
        "kiểm soát truy cập định danh (IAM) — không có cái nào trong số đó được triển khai ở đây."
    )
    lines.append("")
    lines.append(f"ENCRYPT: {'PASS' if encrypt_ok else 'FAIL'}")
    lines.append(f"DECRYPT MATCH: {'PASS' if decrypt_match else 'FAIL'}")
    lines.append("PRODUCTION READY: NO")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print("\n".join(lines[-3:]))


if __name__ == "__main__":
    main()
