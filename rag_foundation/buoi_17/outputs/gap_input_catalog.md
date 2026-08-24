# Buổi 17 — Gap Input Catalog (PROMPT 6)

Nguồn: `data/chunks_combined_secure.csv` — 811 chunk / 25 document.

- EXTERNAL_REQUIREMENT: 15 document
- INTERNAL_POLICY: 10 document
- UNKNOWN (cần rà soát thủ công, KHÔNG dùng cho gap check): 0 document

**Lưu ý bắt buộc**: `INTERNAL_POLICY` ở đây đến từ `agribank_internal_policies.csv` — dữ liệu **MÔ PHỎNG** do học viên tự soạn cho bài thực hành (không phải văn bản nội bộ thật của Agribank), đúng như nguyên tắc "policy trong bài là mô phỏng" của Buổi 17. Không có Thông tư/Nghị định nào bị gán nhãn INTERNAL_POLICY chỉ để chạy demo.

## Danh mục đầy đủ theo document

| document_id | title (rút gọn) | loại văn bản | cơ quan ban hành | classification | n_chunks |
|---|---|---|---|---|---|
| 112025 | Nghị định số 73/2016/NĐ-CP Quy định chi tiết thi hành Luật k | Nghị định | Chính phủ | EXTERNAL_REQUIREMENT | 117 |
| 112924 | Thông tư số 105/2016/TT-BTC Hướng dẫn hoạt động đầu tư gián  | Thông tư | Bộ Tài chính | EXTERNAL_REQUIREMENT | 22 |
| 117310 | Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối v | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 25 |
| 163441 | Nghị định số 46/2023/NĐ-CP Quy định chi tiết thi hành một số | Nghị định | Chính phủ | EXTERNAL_REQUIREMENT | 143 |
| 166269 | Luật Hợp tác xã số 17/2023/QH15 | Luật | Quốc hội | EXTERNAL_REQUIREMENT | 116 |
| 168220 | Thông tư số 27/2024/TT-NHNN Quy định về việc ngân hàng hợp t | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 35 |
| 169221 | Thông tư số 43/2024/TT-NHNN sửa đổi, bổ sung một số điều của | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 5 |
| 173695 | Thông tư số 56/2024/TT-NHNN Quy định hồ sơ, thủ tục cấp Giấy | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 26 |
| 174218 | Thông tư số 62/2024/TT-NHNN Quy định điều kiện, hồ sơ, thủ t | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 31 |
| 177271 | Thông tư số 01/2025/TT-NHNN Quy định về cấp Giấy phép lần đầ | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 22 |
| 185630 | Thông tư số 63/2025/TT-NHNN Sửa đổi, bổ sung một số điều của | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 17 |
| 25692 | Ngân hàng Nhà nước Việt Nam | Luật | Quốc hội | EXTERNAL_REQUIREMENT | 68 |
| 44209 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, | Thông tư | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 74 |
| 6e689cd0-6f81-11f1-94d6-fd5d6d5ff793 | Quy định hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng  | Văn bản hợp nhất | Ngân hàng Nhà nước Việt Nam | EXTERNAL_REQUIREMENT | 46 |
| 95652 | Nghị định số 135/2015/NĐ-CP Quy định về đầu tư gián tiếp ra  | Nghị định | Chính phủ | EXTERNAL_REQUIREMENT | 40 |
| agr_at01 | Quy định nội bộ số 100/QĐ-NHNO-AT về Giao nhận, bảo quản, vậ | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 4 |
| agr_bh06 | Quy định nội bộ số 180/QĐ-NHNO-BH về Mua bảo hiểm rủi ro ngh | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |
| agr_car02 | Quy định nội bộ số 250/QĐ-NHNO-QLRR về Quản lý tỷ lệ an toàn | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 3 |
| agr_fx04 | Quy định nội bộ số 410/QĐ-NHNO-TTNH về Quản lý trạng thái ng | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |
| agr_gp05 | Quy chế số 520/QC-NHNO-MANGLUOI về Mở rộng mạng lưới chi nhá | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |
| agr_hr08 | Quy định nội bộ số 88/QĐ-NHNO-NS về Quy hoạch, bổ nhiệm và q | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |
| agr_it07 | Quy chế bảo mật CNTT số 600/QC-NHNO-CNTT về An toàn thông ti | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |
| agr_tc09 | Quy chế tài chính số 720/QC-NHNO-TC về Chế độ chi tiêu và mu | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |
| agr_td03 | Quy chế tín dụng nội bộ số 315/QC-NHNO-TD về Phán quyết và P | Quy chế nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 3 |
| agr_xln10 | Quy định nội bộ số 390/QĐ-NHNO-XLN về Phân loại nợ và Xử lý  | Quy định nội bộ | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank) | INTERNAL_POLICY | 2 |

## Evidence phân loại (mẫu 5 dòng mỗi loại)

### EXTERNAL_REQUIREMENT

- `112025`: loai_van_ban='Nghị định' (thuộc {'Thông tư', 'Nghị định', 'Luật', 'Văn bản hợp nhất'}), co_quan_ban_hanh='Chính phủ'
- `112924`: loai_van_ban='Thông tư' (thuộc {'Thông tư', 'Nghị định', 'Luật', 'Văn bản hợp nhất'}), co_quan_ban_hanh='Bộ Tài chính'
- `117310`: loai_van_ban='Thông tư' (thuộc {'Thông tư', 'Nghị định', 'Luật', 'Văn bản hợp nhất'}), co_quan_ban_hanh='Ngân hàng Nhà nước Việt Nam'
- `163441`: loai_van_ban='Nghị định' (thuộc {'Thông tư', 'Nghị định', 'Luật', 'Văn bản hợp nhất'}), co_quan_ban_hanh='Chính phủ'
- `166269`: loai_van_ban='Luật' (thuộc {'Thông tư', 'Nghị định', 'Luật', 'Văn bản hợp nhất'}), co_quan_ban_hanh='Quốc hội'

### INTERNAL_POLICY

- `agr_at01`: loai_van_ban='Quy định nội bộ', document_id='agr_at01' bắt đầu bằng 'agr_' (nguồn: agribank_internal_policies.csv, MÔ PHỎNG), co_quan_ban_hanh='Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank)'
- `agr_bh06`: loai_van_ban='Quy định nội bộ', document_id='agr_bh06' bắt đầu bằng 'agr_' (nguồn: agribank_internal_policies.csv, MÔ PHỎNG), co_quan_ban_hanh='Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank)'
- `agr_car02`: loai_van_ban='Quy định nội bộ', document_id='agr_car02' bắt đầu bằng 'agr_' (nguồn: agribank_internal_policies.csv, MÔ PHỎNG), co_quan_ban_hanh='Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank)'
- `agr_fx04`: loai_van_ban='Quy định nội bộ', document_id='agr_fx04' bắt đầu bằng 'agr_' (nguồn: agribank_internal_policies.csv, MÔ PHỎNG), co_quan_ban_hanh='Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank)'
- `agr_gp05`: loai_van_ban='Quy chế nội bộ', document_id='agr_gp05' bắt đầu bằng 'agr_' (nguồn: agribank_internal_policies.csv, MÔ PHỎNG), co_quan_ban_hanh='Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam (Agribank)'

## Kết luận

Có đủ cả hai phía bằng chứng thật (15 external, 10 internal) để chạy Compliance Gap Checker.

COMPLIANCE GAP DATA: READY
