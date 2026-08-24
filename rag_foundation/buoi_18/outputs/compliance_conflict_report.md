# Buổi 18 — Compliance Conflict Report (PROMPT 2 / UC3)

Số cặp đã đối chiếu: **10** (3 miền demo: Kho quỹ, CAR, Tín dụng)

## Phân bố classification

| Classification | Số lượng |
|---|---|
| CHUA_DU_BANG_CHUNG | 5 |
| KHONG_XUNG_DOT | 3 |
| XUNG_DOT | 2 |

## Xung đột phát hiện được: 2

### An toàn kho quỹ & Vận chuyển tiền — Quy trình thực hiện (Severity: LOW)

- **Văn bản A (nội bộ)**: `[100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 30 | doc_agr_at01_04]`
- **Văn bản B (đối chiếu)**: `[01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 41. Quy định vào, ra kho tiền | doc_44209_điều_41__quy_định_vào__ra_kho_tiền_41]`
- **Mô tả**: Văn bản A quy định thành phần Ban Quản lý kho tiền bao gồm 'Giám đốc (hoặc Phó Giám đốc ủy quyền), Kế toán trưởng (hoặc Phụ trách kế toán) và Thủ kho tiền'. Trong khi đó, Văn bản B quy định thứ tự mở/đóng cửa kho tiền cụ thể với 3 vị trí là 'Giám đốc, Trưởng phòng Kế toán, thủ kho tiền' mà không đề cập đến vị trí ủy quyền (Phó Giám đốc ủy quyền) hay Phụ trách kế toán, đồng thời có sự khác biệt về chức danh bộ phận kế toán (Kế toán trưởng ở văn bản A so với Trưởng phòng Kế toán ở văn bản B).
- **Phương pháp**: llm_assisted | review_status: NEEDS_HUMAN_REVIEW

### Quản lý CAR & Rủi ro tín dụng — Hạn mức/ngưỡng (Severity: HIGH)

- **Văn bản A (nội bộ)**: `[250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Điều 18 | doc_agr_car02_02]`
- **Văn bản B (đối chiếu)**: `[41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 9. Hệ số rủi ro tín dụng (CRW) | doc_117310_điều_9__hệ_số_rủi_ro_tín_dụng__crw_9]`
- **Mô tả**: Văn bản A quy định trọng số rủi ro đối với khoản vay bất động sản kinh doanh áp dụng mức từ 150% đến 200% tùy theo tỷ lệ LTV. Ngược lại, Văn bản B (Điểm c Khoản 10 Điều 9) quy định hệ số rủi ro đối với khoản phải đòi được bảo đảm bằng bất động sản kinh doanh theo tỷ lệ LTV chỉ từ 75% đến 120% (dưới 60% là 75%, từ 60% đến dưới 75% là 100%, từ 75% trở lên là 120%).
- **Phương pháp**: llm_assisted | review_status: NEEDS_HUMAN_REVIEW

## Các cặp KHÔNG xung đột / chưa đủ bằng chứng: 8

| Domain | Văn bản A | Văn bản B | Classification | Ghi chú |
|---|---|---|---|---|
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | doc_agr_at01_01] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 59. Định kỳ kiểm tra, kiểm kê | doc_44209_điều_59__định_kỳ_kiểm_tra__kiểm_kê_59] | KHONG_XUNG_DOT | Không có mâu thuẫn giữa hai văn bản. Văn bản A quy định về phạm vi áp dụng và cấm mang chìa khóa kho |
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 12 | doc_agr_at01_02] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 56. Trách nhiệm bảo vệ vận chuyển | doc_44209_điều_56__trách_nhiệm_bảo_vệ_vận_chuyển_56] | KHONG_XUNG_DOT | Không có mâu thuẫn giữa hai văn bản. Khoản 2 Điều 56 của Văn bản B giao quyền cho tổ chức tín dụng t |
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 25 | doc_agr_at01_03] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 11. Giao nhận tiền mặt trong ngành Ngân hàng | doc_44209_điều_11__giao_nhận_tiền_mặt_trong_ngành_ngân_hàng_11] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=60.8) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Quản lý CAR & Rủi ro tín dụng | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Điều 5 | doc_agr_car02_01] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 6. Tỷ lệ an toàn vốn | doc_117310_điều_6__tỷ_lệ_an_toàn_vốn_6] | KHONG_XUNG_DOT | Văn bản đối chiếu yêu cầu tối thiểu 8.0%, nội bộ quy định tối thiểu 8.5% (≥ yêu cầu) — không xung độ |
| Quản lý CAR & Rủi ro tín dụng | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Điều 32 | doc_agr_car02_03] | [27/2024/TT-NHNN - Thông tư số 27/2024/TT-NHNN Quy định về việc ngân hàng hợp tác xã, việc trích nộp, quản lý và sử dụng Quỹ bảo đảm an toàn hệ thống quỹ tín dụng nhân dân | Điều 25. Trích nộp Quỹ bảo toàn | doc_168220_điều_25__trích_nộp_quỹ_bảo_toàn_25] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=83.4) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Tín dụng & Phân cấp phán quyết | [315/QC-NHNO-TD - Quy chế tín dụng nội bộ số 315/QC-NHNO-TD | Điều 8 | doc_agr_td03_01] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 9. Hệ số rủi ro tín dụng (CRW) | doc_117310_điều_9__hệ_số_rủi_ro_tín_dụng__crw_9] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=62.5) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Tín dụng & Phân cấp phán quyết | [315/QC-NHNO-TD - Quy chế tín dụng nội bộ số 315/QC-NHNO-TD | Điều 22 | doc_agr_td03_02] | [17/2023/QH15 - Luật Hợp tác xã số 17/2023/QH15 | Điều 28. Chính sách hỗ trợ hoạt động trong lĩnh vực nông nghiệp | doc_166269_điều_28__chính_sách_hỗ_trợ_hoạt_động_trong_lĩnh_vực_nông_nghiệp_28] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=58.0) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Tín dụng & Phân cấp phán quyết | [315/QC-NHNO-TD - Quy chế tín dụng nội bộ số 315/QC-NHNO-TD | Điều 35 | doc_agr_td03_03] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 9. Hệ số rủi ro tín dụng (CRW) | doc_117310_điều_9__hệ_số_rủi_ro_tín_dụng__crw_9] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=61.4) nhưng không trích xuất được ngưỡng số kiểm chứng đư |

## Kết luận

COMPLIANCE CHECKER ENGINE: PASS
CONFLICTS DETECTED: 2
HUMAN REVIEW GUARDRAIL: PASS
