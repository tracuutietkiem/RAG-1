# Buổi 17 — Dependency Report (PROMPT SETUP + PROMPT 0)

Sinh lúc: chạy `python scripts/inspect_dependencies.py` trên máy học viên.

## 1. Môi trường

- python_version: **3.11.15**
- pandas: **OK**
- rank_bm25: **OK**
- sklearn: **OK**
- neo4j: **OK**

## 2. Ghi chú cấu trúc thực tế (khác với thư mục mẫu trong tài liệu)

Tài liệu Buổi 17 giả định cấu trúc `thuchanh/buoi_16/` + `thuchanh/buoi_17/`. Trên project thực tế của học viên (`RAG/rag_foundation/`), pipeline Hybrid + Rerank + RBAC của các buổi 14/15/16 được gộp chung trong một thư mục **`buoi_14/`** (có `chay_buoi16.bat`, `requirements_buoi16_addon.txt`, `src/secure_retriever.py`, `roles.json` — tức là nội dung RBAC của 'Buổi 15/16' nằm trong `buoi_14/`, không có thư mục `buoi_16/` riêng). Vì vậy Buổi 17 coi **`../buoi_14/`** là nguồn cần tái sử dụng, thay vì `../buoi_16/` như ví dụ trong tài liệu. Không có gì bị sửa hay xoá ở `buoi_14/` để làm việc này.

Ngoài ra, trong `RAG/rag_foundation/buoi_17/` dữ liệu đang nằm lồng một cấp thừa (`buoi_17/buoi_17/Buoi_17.md`, `buoi_17/buoi_17/data/...`). Buổi 17 sẽ được xây ở cấp `buoi_17/` (không lồng thêm); học viên nên dọn thư mục lồng thừa này sau khi xác nhận không cần giữ bản sao cũ.

## 3. Dữ liệu nguồn — chunks_secure.csv vs chunks_normalized.csv

- `chunks_secure.csv`: **2528 dòng, 20 cột**
  - Cột: ['chunk_id', 'document_id', 'text', 'index_text', 'source_file', 'title', 'so_ky_hieu', 'document_type', 'chapter', 'section', 'article', 'clause', 'effective_date', 'status', 'issuing_body', 'signer', 'field', 'citation', 'allowed_roles', 'security_category']
- `chunks_normalized.csv`: **2528 dòng, 18 cột**
  - Cột: ['chunk_id', 'document_id', 'text', 'index_text', 'source_file', 'title', 'so_ky_hieu', 'document_type', 'chapter', 'section', 'article', 'clause', 'effective_date', 'status', 'issuing_body', 'signer', 'field', 'citation']
- Số dòng khớp: **CÓ**
- Cột thêm trong secure so với normalized: `['allowed_roles', 'security_category']`
- Cột thiếu trong secure so với normalized: `không có`
- Kết luận: chunks_secure.csv = chunks_normalized.csv + `allowed_roles` + `security_category` (2 cột thêm, KHÔNG chỉ 1 cột như tài liệu mô tả ở dạng ví dụ — đây là dữ liệu thật của học viên, 2528 dòng, không phải 787 dòng như ví dụ minh hoạ trong bài).

### Danh sách cột đầy đủ cần cho các bước sau

- `chunk_id`: có
- `document_id`: có
- `citation`: có
- `title`: có
- `document_type`: có
- `issuing_body`: có
- `effective_date`: có
- `allowed_roles`: có

## 4. Dữ liệu riêng của Buổi 17 (Compliance Gap Checker)

- `agribank_internal_policies.csv`: **24 dòng, 14 cột** — dữ liệu MÔ PHỎNG quy định nội bộ Agribank (không phải văn bản thật), dùng làm phía INTERNAL_POLICY cho Gap Checker.
- `chunks_combined_secure.csv`: **811 dòng** = 787 external (Thông tư/Nghị định/Luật) + 24 internal (agr_*, mô phỏng Agribank).
- ⚠️ Lưu ý quan trọng: `chunk_id` phía external của `chunks_combined_secure.csv` **KHÔNG trùng namespace** với `chunks_secure.csv` của buoi_14 (giao nhau: 0/787 chunk_id). Đây là một lần chuẩn bị dữ liệu RIÊNG cho Buổi 17 (787 external + 24 internal = 811, đúng với con số 787 dòng mà tài liệu Buổi 17 mô tả), KHÔNG phải cùng một lần chunk hoá với corpus 2528 dòng của buoi_14. Hệ quả: SecureRetriever gốc của buoi_14 (trỏ vào chunks_secure.csv 2528 dòng, không có tài liệu nội bộ) KHÔNG thể trực tiếp tìm điều khoản nội bộ. Compliance Gap Checker (Prompt 6/7) sẽ tái sử dụng THUẬT TOÁN (tokenizer + BM25Okapi + reranker) của buoi_14 nhưng build một chỉ mục riêng, nhỏ, trên `chunks_combined_secure.csv` — không viết lại giải thuật, chỉ trỏ vào corpus đúng phạm vi (có cả nội bộ).

## 5. SecureRetriever (buổi trước)

- File/module: `/home/claude/buoi_17_work/buoi_14/src/secure_retriever.py` (`src.secure_retriever` khi thêm `/home/claude/buoi_17_work/buoi_14` vào sys.path)
- Tồn tại: True
- Import được: True
- Hàm chính tìm thấy: ['secure_search', 'secure_bm25_search', 'secure_dense_search', 'secure_hybrid_search', 'secure_rerank_search', 'filter_records_by_roles', 'visibility_stats']
- Input role: `user_roles` (list[str], validate qua `config.validate_roles`, đọc từ `roles.json` — Admin/HR/Risk_Manager/Staff/Guest)
- Output: dict `{method, user_roles, results, before_rerank, n_total_chunks, n_visible_chunks, n_hidden_chunks}`, mỗi result có chunk_id/document_id/citation/allowed_roles/retrieval_method/score
- Lọc trước hay sau retrieval: BM25: pre-filter DataFrame truoc khi build BM25Okapi (dung nghia den). Dense: post-filter tren cosine score toan corpus nhung FAIL-CLOSED (bo qua chunk khong co quyen, khong bao gio tra ve). Rerank: loc lai LAN NUA (defense-in-depth) ngay truoc khi goi reranker.
- Giữ document_id/chunk_id/citation: KHÔNG xác định

## 6. Kết luận

SOURCE DATA: PASS
RBAC DATA AVAILABLE: YES
SECURE RETRIEVER REUSABLE: YES
REUSE PLAN: Dùng thẳng `buoi_14/src/secure_retriever.secure_search()` qua `secure_retrieval_adapter.py` cho Use Case 1 (tra cứu nội bộ trên corpus 2528 dòng, external-only). Với Compliance Gap Checker, build chỉ mục BM25 nhỏ trên `chunks_combined_secure.csv` (811 dòng, có cả nội bộ), tái sử dụng `tokenize()`, `BM25Okapi`, và `Reranker` (fallback lexical) — không rebuild thuật toán, chỉ đổi nguồn dữ liệu đầu vào cho đúng phạm vi bài toán.
