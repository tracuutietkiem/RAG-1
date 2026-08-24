# Buổi 18 — Security & Guardrail Test Report (PROMPT 5)

| # | Test | Kết quả | Chi tiết |
|---|---|---|---|
| 1 | RBAC - Staff khong truy cap duoc du lieu rieng cua Risk_Manager/Admin | ✅ PASS | Staff bi chan hoan toan khoi agr_car02 (CAR & Rủi ro) sau RBAC filter — đúng. |
| 2 | Citation Integrity - moi conflict/checklist item co citation hop le | ✅ PASS | compliance_conflicts.csv: 10 dòng, 0 XUNG_DOT thiếu citation A; audit_checklist_results.csv: 13 dòng, 0 thiếu source_citation |
| 3 | Hallucination Check - moi citation xuat ra ton tai that trong dataset | ✅ PASS | compliance_conflicts.csv: 0 citation KHÔNG khớp dataset gốc; audit_checklist_results.csv: 0 citation KHÔNG khớp dataset gốc |
| 4 | Human Review Guardrail - moi ket qua co review_status=NEEDS_HUMAN_REVIEW | ✅ PASS | compliance_conflicts.csv: 10 dòng, 0 dòng SAI review_status; audit_checklist_results.csv: 13 dòng, 0 dòng SAI review_status |
| 5 | Audit Log Privacy - khong luu API key/secret, da redact | ✅ PASS | API key thật không xuất hiện trong log; pattern secret khả nghi chưa redact: không có. |
| 6 | Unknown Domain Test - khong bia du lieu khi domain khong ton tai | ✅ PASS | Domain không có dữ liệu -> trả về danh sách rỗng, KHÔNG bịa checklist. |
| 7 | File Export Verification - CSV dung schema, mo duoc | ✅ PASS | compliance_conflicts.csv: 10 dòng, thiếu cột: không; audit_checklist_results.csv: 13 dòng, thiếu cột: không |

## Kết luận

SECURITY & GUARDRAIL TESTS: PASS
