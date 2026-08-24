# Buổi 17 — Security Test Report (PROMPT 10)

| # | Test | Kết quả | Chi tiết |
|---|---|---|---|
| 1 | Role được phép nhận kết quả | ✅ PASS | n_results=3 |
| 2 | Role không được phép không thấy text/citation hạn chế | ✅ PASS | leaked_chunk_ids=none |
| 3 | Tài liệu bị cấm không vào context (kể cả before_rerank) | ✅ PASS | unauthorized_in_context=none |
| 4 | Unknown role bị DENY | ✅ PASS | ValueError: Vai tro khong hop le: 'ROLE_KHONG_TON_TAI'. Cac vai tro hop le: ['Admin', 'HR', 'Risk_Manager', 'Staff', 'Guest'] |
| 5 | Audit ghi cả SUCCESS và DENIED | ✅ PASS | statuses_found=['DENIED', 'SUCCESS'] |
| 6 | Log không chứa password/API key | ✅ PASS | suspect_lines=none |
| 7 | Citation tồn tại trên mọi kết quả | ✅ PASS | n_checked=3 |
| 8 | Mọi gap có evidence hoặc là CHUA_DU_BANG_CHUNG | ✅ PASS | rows_thieu_evidence=0 |
| 9 | Mọi gap result có review_status=NEEDS_HUMAN_REVIEW | ✅ PASS | n_rows=787 |
| 10 | Neo4j trạng thái được báo cáo trung thực (không giả định) | ✅ PASS | ok=True, message='Neo4j san sang' |

SECURITY TESTS: PASS
