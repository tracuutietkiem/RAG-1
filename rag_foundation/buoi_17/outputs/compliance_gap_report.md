# Buổi 17 — Compliance Gap Report (PROMPT 7)

Đã chấm điểm **787** yêu cầu bên ngoài (EXTERNAL_REQUIREMENT, toàn bộ 787 chunk) đối chiếu với **24** điều khoản nội bộ mô phỏng (INTERNAL_POLICY), dùng BM25 (tái sử dụng `tokenize()` + `BM25Okapi` của buoi_14, không viết lại thuật toán retrieval).

Neo4j status: Neo4j san sang (GRAPH USED: NO, xem chi tiết ở graph_gap_integration_report.md)

LLM hỗ trợ phân loại (tuỳ chọn, cần `GEMINI_API_KEY`): BẬT.

## Vì sao không có THIẾU tự động (nếu 0)

Corpus nội bộ mô phỏng chỉ có 24 chunk / 10 văn bản. Với BM25 trên một corpus nhỏ như vậy, hầu như MỌI yêu cầu bên ngoài đều tìm được một văn bản nội bộ "gần giống nhất" với điểm > 0, kể cả khi chỉ trùng từ khoá hành chính chung (đã kiểm chứng: toàn bộ 62 chunk chứa cụm bắt buộc như "kiểm toán nội bộ" đều có ứng viên nội bộ với ratio điểm/trung bình > 1.5). Vì hệ thống rule-based không đọc hiểu ngữ nghĩa để phân biệt "internal doc thực sự không cover yêu cầu này" với "chỉ trùng từ khoá", việc tự gán THIẾU trong trường hợp đó sẽ là suy đoán, vi phạm nguyên tắc "Không tự bịa gap" của bài. THIẾU/CHÊNH_LỆCH chỉ được gán tự động khi có **ngưỡng số cụ thể, kiểm chứng được, trên cả hai phía** (tỷ lệ % tối thiểu, hạn mức tiền tệ). Khi có `GEMINI_API_KEY`, hệ thống dùng thêm một bước LLM-assisted (tối đa 25 lần gọi/lần chạy) đọc trực tiếp hai văn bản để đề xuất phân loại tinh hơn — nhưng vẫn luôn `NEEDS_HUMAN_REVIEW`.

## Phân bố phân loại

- DAP_UNG: 1
- CHENH_LECH: 0
- THIEU: 0
- CHUA_DU_BANG_CHUNG: 786

## Bảng ví dụ (mỗi loại tối đa 5 dòng)

### DAP_UNG

| gap_id | external_citation | internal_citation | reason | confidence |
|---|---|---|---|---|
| gap_e155b16f3c | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ l | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Đi | Yêu cầu bên ngoài: tối thiểu 8.0%. Nội bộ quy định: tối thiểu 8.5% (≥ yêu cầu) — evidence: 'tối thiểu 8%' vs 'tối thiểu  | 0.85 |

### CHUA_DU_BANG_CHUNG

| gap_id | external_citation | internal_citation | reason | confidence |
|---|---|---|---|---|
| gap_03527edd2d | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=103.1) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceili | 0.35 |
| gap_e56ce15c8f | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=93.3) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceilin | 0.35 |
| gap_a79274508e | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=50.9) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceilin | 0.35 |
| gap_55b4bbeaa3 | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=157.2) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceili | 0.35 |
| gap_18d4b68feb | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 3 | Ứng viên nội bộ gần nhất (BM25 score=104.5) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceili | 0.35 |

## Ràng buộc đã tuân thủ

- Không kết luận chỉ từ similarity score (dùng regex ngưỡng số + evidence 2 phía).
- Không gán DAP_UNG khi không có internal evidence (luôn kiểm tra `internal_row is None` trước).
- Không gán THIẾU chỉ vì retriever chưa tìm thấy — chỉ gán khi có cụm bắt buộc rõ ràng trong văn bản bên ngoài.
- Mọi dòng đều có `review_status = NEEDS_HUMAN_REVIEW`.

GAP CHECKER: PASS
HUMAN REVIEW REQUIRED: YES
