# Buổi 17 — RBAC, Audit Trail và AI Compliance Gap Checker

Trạng thái: **READY FOR DEMO: YES** (xem `outputs/final_validation_report.md`).

## Cách chạy lại toàn bộ (đúng thứ tự)

```bash
# (khuyến nghị) dùng backend offline để không phải tải model ~2GB:
export DENSE_BACKEND=lsa RERANKER_BACKEND=fallback

python scripts/inspect_dependencies.py        # PROMPT 0
python scripts/rbac_reuse_check.py            # PROMPT 1
python scripts/secure_retrieval_adapter.py    # PROMPT 2 (smoke test)
python scripts/secure_retrieval_test.py       # PROMPT 2 (test đầy đủ)
python scripts/audit_logger.py                # PROMPT 3
python scripts/encryption_demo.py             # PROMPT 4
python scripts/internal_lookup.py             # PROMPT 5
python scripts/gap_input_catalog.py           # PROMPT 6
python scripts/compliance_gap.py              # PROMPT 7
python scripts/graph_gap_integration_check.py # PROMPT 8
streamlit run app.py                          # PROMPT 9
python scripts/security_tests.py              # PROMPT 10
python scripts/final_validation.py            # PROMPT 11
```

Mỗi script ghi báo cáo tương ứng vào `outputs/`.

## Ghi chú cấu trúc quan trọng (khác với tài liệu mẫu)

1. **`buoi_16/` không tồn tại như một thư mục riêng.** Trên project thực tế,
   pipeline Hybrid + Rerank + RBAC (Buổi 14/15/16 gộp lại) nằm trong
   `../buoi_14/`. Buổi 17 coi `../buoi_14/` là nguồn tái sử dụng. Chi tiết:
   `outputs/dependency_report.md`.

2. **Có hai bộ dữ liệu, KHÔNG trộn lẫn:**
   - `../buoi_14/data/processed/chunks_secure.csv` (2528 dòng, chỉ có văn
     bản bên ngoài NHNN/Chính phủ/Quốc hội) — dùng cho Use Case 1 (tra cứu
     nội bộ qua RBAC) thông qua `secure_retrieval_adapter.py`, gọi thẳng
     `SecureRetriever` của buoi_14, **không viết lại**.
   - `data/chunks_combined_secure.csv` (811 dòng = 787 external + 24
     internal mô phỏng từ `data/agribank_internal_policies.csv`) — dùng
     riêng cho Compliance Gap Checker (PROMPT 6/7), vì corpus chính của
     buoi_14 không có bất kỳ văn bản nội bộ nào để đối chiếu.

3. **Thư mục `RAG/rag_foundation/buoi_17/buoi_17/` bị lồng thừa một cấp**
   trên máy học viên (dữ liệu nằm ở `buoi_17/buoi_17/Buoi_17.md` và
   `buoi_17/buoi_17/data/...` thay vì `buoi_17/Buoi_17.md`). Toàn bộ Buổi 17
   được xây ở đúng cấp `buoi_17/` (thư mục này) — nên dọn thư mục con lồng
   thừa sau khi xác nhận không cần giữ bản sao cũ.

4. **Không có `config/rbac_policy.json` riêng** — xem `config/README.md`
   để biết lý do (tái sử dụng `../buoi_14/roles.json`, không tạo bản sao).

5. **Compliance Gap Checker không tự gán THIẾU/CHÊNH_LỆCH từ suy đoán từ
   khoá.** Với corpus nội bộ chỉ 24 chunk, BM25 gần như luôn tìm được một
   "ứng viên gần nhất" dù chỉ trùng từ khoá hành chính chung — nên hệ thống
   CHỈ tự động gán DAP_UNG/CHENH_LECH khi có ngưỡng số (%, hạn mức tiền tệ)
   kiểm chứng được trên CẢ HAI phía; mọi trường hợp khác là
   `CHUA_DU_BANG_CHUNG`. Có hỗ trợ tuỳ chọn qua LLM (Gemini) nếu điền
   `GEMINI_API_KEY` vào `.env` — script sẽ tự phát hiện và dùng thêm bước
   LLM-assisted (vẫn luôn `NEEDS_HUMAN_REVIEW`). Chi tiết:
   `outputs/compliance_gap_report.md`, mục "Vì sao không có THIẾU tự động".

6. **Neo4j**: không kết nối được từ môi trường build này (không phải máy
   Windows của học viên). `outputs/graph_gap_integration_report.md` giải
   thích rõ và khuyến nghị chạy lại `scripts/graph_gap_integration_check.py`
   trên máy có Neo4j Desktop đang mở để xác nhận sống.

## Danh sách output

Xem `outputs/` — mỗi PROMPT có báo cáo `.md` riêng, cộng
`compliance_gap_results.csv` và `audit_log.jsonl`.

## Nhắc lại nguyên tắc của buổi học

AI Compliance Gap Checker **không phải kết luận kiểm toán cuối cùng** — mọi
finding đều `NEEDS_HUMAN_REVIEW`. Kiểm toán viên phải tự đối chiếu với quy
định hiện hành của Agribank và Ngân hàng Nhà nước trước khi sử dụng.
