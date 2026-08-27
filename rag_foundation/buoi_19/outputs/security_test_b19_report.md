# Buổi 19 — Security & Local Guardrail Test Report (PROMPT 5)

LLM_PROVIDER lúc chạy test: `ollama`

| # | Test | Kết quả | Chi tiết |
|---|---|---|---|
| 1 | Local Offline Privacy Check - khong goi ra Internet khi LLM_PROVIDER=ollama | ✅ PASS | LLM_PROVIDER=ollama, OLLAMA_BASE_URL=http://localhost:11434 (host='localhost', is_local=True), _call_gemini đã bị gọi trong pipeline: False (False là đúng khi provider=ollama — không có đường nào rời khỏi mạng cục bộ). |
| 2 | RBAC Enforcement - Staff bi chan 100% du lieu bao mat rui ro | ✅ PASS | Staff bị chặn hoàn toàn khỏi agr_car02 (CAR & Rủi ro) sau RBAC filter — đúng. |
| 3 | Citation Integrity - moi ket qua tu Qwen3:0.6b/Gemini co trich dan Dieu/Khoan hop le | ✅ PASS | compliance_conflicts.csv: 10 dòng, 0 XUNG_DOT thiếu citation, 0 citation không khớp dataset thật; audit_checklist_results.csv: 16 dòng, 0 thiếu citation, 0 citation không khớp dataset thật |
| 4 | Human Review Guardrail - 100% ket qua co review_status=NEEDS_HUMAN_REVIEW | ✅ PASS | compliance_conflicts.csv: 10 dòng, 0 dòng SAI review_status; audit_checklist_results.csv: 16 dòng, 0 dòng SAI review_status |
| 5 | Audit Log Privacy - khong lo API key/secret trong log | ✅ PASS | API key thật không xuất hiện trong log; pattern secret khả nghi chưa redact: không có. |
| 6 | Local Model Resilience - he thong van phan hoi binh thuong khi mat Internet/cloud | ✅ PASS | UC3: 4 cặp, NEEDS_HUMAN_REVIEW=đủ; UC4: 9 mục checklist, NEEDS_HUMAN_REVIEW=đủ — cả hai vẫn phản hồi bình thường dù đường Internet/cloud bị chặn hoàn toàn. |

## Kết luận

SECURITY & GUARDRAIL TESTS: PASS
