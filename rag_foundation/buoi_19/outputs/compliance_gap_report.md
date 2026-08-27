# Buổi 19 — Compliance Gap Report (PROMPT 2 / UC2, provider=ollama)

Đã chấm điểm **787** yêu cầu bên ngoài (EXTERNAL_REQUIREMENT, toàn bộ 787 chunk) đối chiếu với **24** điều khoản nội bộ mô phỏng (INTERNAL_POLICY), dùng BM25 (tái sử dụng `tokenize()` + `BM25Okapi` của buoi_14, không viết lại thuật toán retrieval).

Neo4j status: Neo4j chua san sang: thieu ['NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD'] trong .env (GRAPH USED: NO)

LLM_PROVIDER hiện tại: **ollama** (Ollama local hoặc Gemini cloud tuỳ .env)

## Phân bố phân loại

- DAP_UNG: 1
- CHENH_LECH: 0
- THIEU: 0
- CHUA_DU_BANG_CHUNG: 786

## Bảng ví dụ (mỗi loại tối đa 5 dòng)

### DAP_UNG

| gap_id | external_citation | internal_citation | reason | confidence |
|---|---|---|---|---|
| gap_fbc93e7620 | [41/2016/TT-NHNN - Thông tư số 41/2016/TT-NHNN Quy định tỷ l | [250/QĐ-NHNO-QLRR - Quy định nội bộ số 250/QĐ-NHNO-QLRR | Đi | Yêu cầu bên ngoài: tối thiểu 8.0%. Nội bộ quy định: tối thiểu 8.5% (≥ yêu cầu) — evidence: 'tối thiểu 8%' vs 'tối thiểu  | 0.85 |

### CHUA_DU_BANG_CHUNG

| gap_id | external_citation | internal_citation | reason | confidence |
|---|---|---|---|---|
| gap_a107709b90 | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=103.1) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceili | 0.35 |
| gap_661c089802 | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=93.3) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceilin | 0.35 |
| gap_aba10294f8 | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=50.9) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceilin | 0.35 |
| gap_a359e248dc | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 1 | Ứng viên nội bộ gần nhất (BM25 score=157.2) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceili | 0.35 |
| gap_d809c66b0e | [01/2014/TT-NHNN - Thông tư số 01/2014/TT-NHNN Quy định về g | [100/QĐ-NHNO-AT - Quy định nội bộ số 100/QĐ-NHNO-AT | Điều 3 | Ứng viên nội bộ gần nhất (BM25 score=104.5) không có ngưỡng số/tiêu chí có thể đối chiếu tự động (không phải floor/ceili | 0.35 |

## Ràng buộc đã tuân thủ

- Không kết luận chỉ từ similarity score (dùng regex ngưỡng số + evidence 2 phía).
- Không gán DAP_UNG khi không có internal evidence.
- Không gán THIẾU chỉ vì retriever chưa tìm thấy.
- Mọi dòng đều có `review_status = NEEDS_HUMAN_REVIEW`.

GAP CHECKER: PASS
HUMAN REVIEW REQUIRED: YES
