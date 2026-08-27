# Buổi 19 — Compliance Conflict Report (PROMPT 2 / UC3, provider=ollama)

Số cặp đã đối chiếu: **10** (3 miền demo: Kho quỹ, CAR, Tín dụng)

## Phân bố classification

| Classification | Số lượng |
|---|---|
| CHUA_DU_BANG_CHUNG | 7 |
| KHONG_XUNG_DOT | 3 |

## Xung đột phát hiện được: 0

## Các cặp KHÔNG xung đột / chưa đủ bằng chứng: 10

| Domain | Văn bản A | Văn bản B | Classification | Ghi chú |
|---|---|---|---|---|
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | doc_agr_at01_01] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 59. Định kỳ kiểm tra, kiểm kê | doc_44209_điều_59__định_kỳ_kiểm_tra__kiểm_kê_59] | KHONG_XUNG_DOT | Văn bản A và B không có đoạn văn nào liên quan đến quy định nội bộ Agribank. Vì vậy, không có sự sao |
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 12 | doc_agr_at01_02] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 56. Trách nhiệm bảo vệ vận chuyển | doc_44209_điều_56__trách_nhiệm_bảo_vệ_vận_chuyển_56] | KHONG_XUNG_DOT | Văn bản A và B không có sự đối chiếu trực tiếp, không có thông tin từ A hoặc B để suy luận về quy đị |
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 25 | doc_agr_at01_03] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 11. Giao nhận tiền mặt trong ngành Ngân hàng | doc_44209_điều_11__giao_nhận_tiền_mặt_trong_ngành_ngân_hàng_11] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=60.8) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| An toàn kho quỹ & Vận chuyển tiền | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 30 | doc_agr_at01_04] | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá | Điều 41. Quy định vào, ra kho tiền | doc_44209_điều_41__quy_định_vào__ra_kho_tiền_41] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=82.0) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Quản lý CAR & Rủi ro tín dụng | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Điều 5 | doc_agr_car02_01] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 6. Tỷ lệ an toàn vốn | doc_117310_điều_6__tỷ_lệ_an_toàn_vốn_6] | KHONG_XUNG_DOT | Văn bản đối chiếu yêu cầu tối thiểu 8.0%, nội bộ quy định tối thiểu 8.5% (≥ yêu cầu) — không xung độ |
| Quản lý CAR & Rủi ro tín dụng | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Điều 18 | doc_agr_car02_02] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 9. Hệ số rủi ro tín dụng (CRW) | doc_117310_điều_9__hệ_số_rủi_ro_tín_dụng__crw_9] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=113.1) nhưng không trích xuất được ngưỡng số kiểm chứng đ |
| Quản lý CAR & Rủi ro tín dụng | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Điều 32 | doc_agr_car02_03] | [27/2024/TT-NHNN - Thông tư số 27/2024/TT-NHNN Quy định về việc ngân hàng hợp tác xã, việc trích nộp, quản lý và sử dụng Quỹ bảo đảm an toàn hệ thống quỹ tín dụng nhân dân | Điều 25. Trích nộp Quỹ bảo toàn | doc_168220_điều_25__trích_nộp_quỹ_bảo_toàn_25] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=83.4) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Tín dụng & Phân cấp phán quyết | [315/QC-NHNO-TD - Quy chế tín dụng nội bộ số 315/QC-NHNO-TD | Điều 8 | doc_agr_td03_01] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 9. Hệ số rủi ro tín dụng (CRW) | doc_117310_điều_9__hệ_số_rủi_ro_tín_dụng__crw_9] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=62.5) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Tín dụng & Phân cấp phán quyết | [315/QC-NHNO-TD - Quy chế tín dụng nội bộ số 315/QC-NHNO-TD | Điều 22 | doc_agr_td03_02] | [17/2023/QH15 - Luật Hợp tác xã số 17/2023/QH15 | Điều 28. Chính sách hỗ trợ hoạt động trong lĩnh vực nông nghiệp | doc_166269_điều_28__chính_sách_hỗ_trợ_hoạt_động_trong_lĩnh_vực_nông_nghiệp_28] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=58.0) nhưng không trích xuất được ngưỡng số kiểm chứng đư |
| Tín dụng & Phân cấp phán quyết | [315/QC-NHNO-TD - Quy chế tín dụng nội bộ số 315/QC-NHNO-TD | Điều 35 | doc_agr_td03_03] | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài | Điều 9. Hệ số rủi ro tín dụng (CRW) | doc_117310_điều_9__hệ_số_rủi_ro_tín_dụng__crw_9] | CHUA_DU_BANG_CHUNG | Có văn bản đối chiếu liên quan (BM25 score=61.4) nhưng không trích xuất được ngưỡng số kiểm chứng đư |

## Kết luận

LLM_PROVIDER: ollama
COMPLIANCE CHECKER ENGINE: PASS
CONFLICTS DETECTED: 0
HUMAN REVIEW GUARDRAIL: PASS
