# Buổi 18 — Data Catalog Report (PROMPT 1)

## 1. Danh mục văn bản nội bộ Agribank

| document_id | Số ký hiệu | Loại văn bản | Cơ quan ban hành | Ngày ban hành | Domain | Số chunk |
|---|---|---|---|---|---|---|
| agr_at01 | 100/QĐ-NHNO-AT | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 15/03/2024 | An toàn kho quỹ & Vận chuyển tiền | 4 |
| agr_car02 | 250/QĐ-NHNO-QLRR | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 20/06/2024 | Quản lý CAR & Rủi ro tín dụng | 3 |
| agr_td03 | 315/QC-NHNO-TD | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 10/01/2024 | Tín dụng & Phân cấp phán quyết | 3 |
| agr_fx04 | 410/QĐ-NHNO-TTNH | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 05/09/2024 | Ngoại tệ & Kinh doanh ngoại hối | 2 |
| agr_gp05 | 520/QC-NHNO-MANGLUOI | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 18/11/2024 | Mạng lưới & Mở rộng chi nhánh | 2 |
| agr_bh06 | 180/QĐ-NHNO-BH | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 14/02/2024 | Bảo hiểm rủi ro nghiệp vụ | 2 |
| agr_it07 | 600/QC-NHNO-CNTT | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 01/03/2025 | Bảo mật CNTT & AI | 2 |
| agr_hr08 | 88/QĐ-NHNO-NS | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 10/01/2025 | Nhân sự & Quy hoạch cán bộ | 2 |
| agr_tc09 | 720/QC-NHNO-TC | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 05/12/2024 | Tài chính & Mua sắm nội bộ | 2 |
| agr_xln10 | 390/QĐ-NHNO-XLN | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | 22/07/2024 | Phân loại nợ & Xử lý nợ xấu | 2 |

Tổng số văn bản nội bộ: **10**  
Tổng số chunk nội bộ: **24**

## 2. Phân bố chunk nội bộ theo Domain

| Domain | Số văn bản | Số chunk |
|---|---|---|
| An toàn kho quỹ & Vận chuyển tiền | 1 | 4 |
| Quản lý CAR & Rủi ro tín dụng | 1 | 3 |
| Tín dụng & Phân cấp phán quyết | 1 | 3 |
| Ngoại tệ & Kinh doanh ngoại hối | 1 | 2 |
| Mạng lưới & Mở rộng chi nhánh | 1 | 2 |
| Bảo hiểm rủi ro nghiệp vụ | 1 | 2 |
| Bảo mật CNTT & AI | 1 | 2 |
| Nhân sự & Quy hoạch cán bộ | 1 | 2 |
| Tài chính & Mua sắm nội bộ | 1 | 2 |
| Phân loại nợ & Xử lý nợ xấu | 1 | 2 |

## 3. Kiểm tra đầy đủ 14 trường metadata

Cột thiếu (so với schema chuẩn 14 cột): không có

Kiểm tra riêng 3 trường bắt buộc cho UC3/UC4 (`article`, `citation`, `allowed_roles`):

| Trường | Số dòng rỗng | Ví dụ |
|---|---|---|
| `article` | 0 | Điều 1. Phạm vi và đối tượng tuân thủ |
| `citation` | 0 | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | doc_agr_at01_01] |
| `allowed_roles` | 0 | ["Admin", "Risk_Manager", "Staff"] |

## 4. `chunks_combined_secure.csv` (dùng để retrieval đối chiếu ngoài)

- Tổng: 811 chunk (nội bộ mô phỏng: 24, pháp lý bên ngoài: 787)
- Phân bố `loai_van_ban` (bên ngoài): {'Nghị định': 300, 'Thông tư': 257, 'Luật': 184, 'Văn bản hợp nhất': 46}

## Kết luận

DATA CATALOGING: PASS
DOMAINS DETECTED: 10
READY FOR UC3 & UC4: YES
