# Buổi 17 — Encryption Demo Report (PROMPT 4)

**Mục tiêu**: minh hoạ bảo vệ dữ liệu at-rest bằng mã hoá đối xứng (Fernet/AES). Đây CHỈ là demo giáo dục — KHÔNG phải giải pháp bảo mật production.

## Kết quả

- File nguồn: `outputs/audit_log.jsonl` (2556 bytes)
- Key: sinh ngẫu nhiên bằng `Fernet.generate_key()`, lưu tại `outputs/audit_log_demo.key` (đã có trong `.gitignore`, KHÔNG hard-code trong source)
- File mã hoá: `outputs/audit_log_demo.enc` (3492 bytes)
- SHA256 gốc:    `0c18d01fcf2bba38fb97d835ca8ca1b1bf902b2c45fb97af786061fd6ca7a905`
- SHA256 sau khi giải mã: `0c18d01fcf2bba38fb97d835ca8ca1b1bf902b2c45fb97af786061fd6ca7a905`
- Encrypt thành công: CÓ
- Decrypt khớp 100% với bản gốc: CÓ

## Giới hạn (học viên PHẢI hiểu rõ)

Demo này chỉ chứng minh cơ chế mã hoá/giải mã hoạt động đúng trên một file cụ thể. Một hệ thống thật còn cần thêm: TLS cho dữ liệu truyền tải (in-transit), quản lý vòng đời khoá (key management/rotation) qua KMS/HSM chuyên dụng, sao lưu (backup) có mã hoá, và kiểm soát truy cập định danh (IAM) — không có cái nào trong số đó được triển khai ở đây.

ENCRYPT: PASS
DECRYPT MATCH: PASS
PRODUCTION READY: NO
