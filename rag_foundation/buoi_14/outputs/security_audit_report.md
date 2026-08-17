# Báo cáo Kiểm định Bảo mật (Security Audit) — Buổi 15

- Thời điểm chạy: 2026-08-17T13:01:15
- Nguồn dữ liệu: `data/processed/chunks_secure.csv`
- Vai trò hệ thống: `['Admin', 'HR', 'Risk_Manager', 'Staff', 'Guest']`
- Ngưỡng kiểm tra rò rỉ: Top-10 (candidate_k=30), 4 phương pháp: `bm25, dense, hybrid, hybrid_rerank`

## 1. Tổng quan

- Tổng số test case: **5**
- Tổng số lượt kiểm tra rò rỉ (test case × phương pháp): **20**
- PASS: **5** / FAIL: **0**

## 2. Kết quả từng test case

| # | Test case | Target chunk | Unauthorized roles | Authorized roles | Kết quả |
|---|---|---|---|---|---|
| 1 | HR-01 · Bổ nhiệm Trưởng kiểm toán nội bộ | `27257_D14_023` | `['Guest']` | `['HR']` | ✅ PASS |
| 2 | HR-02 · Miễn nhiệm Chủ tịch HĐQT | `166170_D46_062` | `['Staff']` | `['Admin']` | ✅ PASS |
| 3 | HR-03 · Nhiệm kỳ Tổng giám đốc | `166170_D22_027` | `['Risk_Manager']` | `['HR']` | ✅ PASS |
| 4 | RISK-01 · Giới hạn cấp tín dụng | `166170_D136K1_214` | `['Guest']` | `['Risk_Manager']` | ✅ PASS |
| 5 | RISK-02 · Quản lý khoản cấp tín dụng có vấn đề | `186888_D33_052` | `['HR']` | `['Staff']` | ✅ PASS |

## 3. Bằng chứng kiểm thử chi tiết

### 1. HR-01 · Bổ nhiệm Trưởng kiểm toán nội bộ — PASS

- Câu hỏi: *Thẩm quyền bổ nhiệm, miễn nhiệm Trưởng kiểm toán nội bộ của tổ chức tín dụng*
- Tài liệu nhạy cảm đích: `27257_D14_023` (văn bản `27257`)
- Vai trò KHÔNG được phép: `['Guest']`
- Vai trò ĐƯỢC phép: `['HR']`

| Phương pháp | Rò rỉ với unauthorized_roles? | Xuất hiện với authorized_roles? | Rank (authorized) |
|---|---|---|---|
| bm25 | Không (an toàn) | Có | 1 |
| dense | Không (an toàn) | Có | 2 |
| hybrid | Không (an toàn) | Có | 1 |
| hybrid_rerank | Không (an toàn) | Có | 2 |

> ✅ **Bằng chứng PASS:** với vai trò `['Guest']`, không có phương pháp nào trong `['bm25', 'dense', 'hybrid', 'hybrid_rerank']` trả về chunk `27257_D14_023` trong Top-10.

### 2. HR-02 · Miễn nhiệm Chủ tịch HĐQT — PASS

- Câu hỏi: *Miễn nhiệm, bãi nhiệm Chủ tịch Hội đồng quản trị tổ chức tín dụng*
- Tài liệu nhạy cảm đích: `166170_D46_062` (văn bản `166170`)
- Vai trò KHÔNG được phép: `['Staff']`
- Vai trò ĐƯỢC phép: `['Admin']`

| Phương pháp | Rò rỉ với unauthorized_roles? | Xuất hiện với authorized_roles? | Rank (authorized) |
|---|---|---|---|
| bm25 | Không (an toàn) | Có | 1 |
| dense | Không (an toàn) | Có | 3 |
| hybrid | Không (an toàn) | Có | 1 |
| hybrid_rerank | Không (an toàn) | Có | 1 |

> ✅ **Bằng chứng PASS:** với vai trò `['Staff']`, không có phương pháp nào trong `['bm25', 'dense', 'hybrid', 'hybrid_rerank']` trả về chunk `166170_D46_062` trong Top-10.

### 3. HR-03 · Nhiệm kỳ Tổng giám đốc — PASS

- Câu hỏi: *Nhiệm kỳ và trách nhiệm của Tổng giám đốc ngân hàng chính sách*
- Tài liệu nhạy cảm đích: `166170_D22_027` (văn bản `166170`)
- Vai trò KHÔNG được phép: `['Risk_Manager']`
- Vai trò ĐƯỢC phép: `['HR']`

| Phương pháp | Rò rỉ với unauthorized_roles? | Xuất hiện với authorized_roles? | Rank (authorized) |
|---|---|---|---|
| bm25 | Không (an toàn) | Có | 1 |
| dense | Không (an toàn) | Có | 1 |
| hybrid | Không (an toàn) | Có | 1 |
| hybrid_rerank | Không (an toàn) | Có | 3 |

> ✅ **Bằng chứng PASS:** với vai trò `['Risk_Manager']`, không có phương pháp nào trong `['bm25', 'dense', 'hybrid', 'hybrid_rerank']` trả về chunk `166170_D22_027` trong Top-10.

### 4. RISK-01 · Giới hạn cấp tín dụng — PASS

- Câu hỏi: *Giới hạn cấp tín dụng đối với một khách hàng và người có liên quan*
- Tài liệu nhạy cảm đích: `166170_D136K1_214` (văn bản `166170`)
- Vai trò KHÔNG được phép: `['Guest']`
- Vai trò ĐƯỢC phép: `['Risk_Manager']`

| Phương pháp | Rò rỉ với unauthorized_roles? | Xuất hiện với authorized_roles? | Rank (authorized) |
|---|---|---|---|
| bm25 | Không (an toàn) | Có | 1 |
| dense | Không (an toàn) | Có | 4 |
| hybrid | Không (an toàn) | Có | 2 |
| hybrid_rerank | Không (an toàn) | Có | 2 |

> ✅ **Bằng chứng PASS:** với vai trò `['Guest']`, không có phương pháp nào trong `['bm25', 'dense', 'hybrid', 'hybrid_rerank']` trả về chunk `166170_D136K1_214` trong Top-10.

### 5. RISK-02 · Quản lý khoản cấp tín dụng có vấn đề — PASS

- Câu hỏi: *Quản lý khoản cấp tín dụng có vấn đề tại tổ chức tín dụng*
- Tài liệu nhạy cảm đích: `186888_D33_052` (văn bản `186888`)
- Vai trò KHÔNG được phép: `['HR']`
- Vai trò ĐƯỢC phép: `['Staff']`

| Phương pháp | Rò rỉ với unauthorized_roles? | Xuất hiện với authorized_roles? | Rank (authorized) |
|---|---|---|---|
| bm25 | Không (an toàn) | Có | 1 |
| dense | Không (an toàn) | Có | 14 |
| hybrid | Không (an toàn) | Có | 2 |
| hybrid_rerank | Không (an toàn) | Có | 3 |

> ✅ **Bằng chứng PASS:** với vai trò `['HR']`, không có phương pháp nào trong `['bm25', 'dense', 'hybrid', 'hybrid_rerank']` trả về chunk `186888_D33_052` trong Top-10.

## 4. Kết luận

✅ **Hệ thống ĐẠT chứng nhận an toàn dữ liệu mức cơ bản** — toàn bộ 20 lượt kiểm tra rò rỉ (5 test case × 4 phương pháp) đều PASS. Không phát hiện trường hợp vai trò không đủ quyền nhìn thấy tài liệu nhạy cảm của vai trò khác, ở cả 3 tầng: BM25 (pre-filter DataFrame), Dense (post-filter metadata), và Hybrid + Reranker (candidate đã lọc quyền trước khi vào Reranker).

> Lưu ý: test case này chỉ kiểm tra tầng BM25 / Dense / Hybrid / Reranker (dữ liệu CSV). Tầng Graph (Neo4j) được kiểm tra riêng qua `src.secure_retriever.secure_graph_hints()` — chạy `python scripts/secure_search_demo.py` với Neo4j đang hoạt động để quan sát trực tiếp.