# Buổi 17 — RBAC Reuse Report (PROMPT 1)

## 1. Phân tích allowed_roles (chunks_secure.csv, buoi_14, nguồn thật)

- Tổng số chunk: 2528
- Số chunk theo từng role (một chunk có thể thuộc nhiều role):
  - `Admin`: 2528 chunk (100.0%)
  - `Risk_Manager`: 2050 chunk (81.1%)
  - `Staff`: 2050 chunk (81.1%)
  - `HR`: 1706 chunk (67.5%)
  - `Guest`: 1228 chunk (48.6%)
- Chunk có >1 role được phép xem: 2528
- Chunk chỉ có đúng 1 role được phép xem: 0
- Số role tối thiểu trên một chunk: 2 (không có chunk nào bị khoá cho đúng 1 mình 1 role không phải Admin trong tập dữ liệu này — nghĩa là dữ liệu thật không tạo ra trường hợp 'chunk riêng tư tuyệt đối', nhưng Guest vẫn chỉ thấy 1228/2528 = 48.6% do phần lớn thuộc nhóm RISK/HR)
- Chunk không parse được allowed_roles: 0
- Format allowed_roles: chuỗi JSON list (vd `["Admin", "HR"]`), parse ổn định 100% bằng `json.loads`; hàm phân tích ở đây fallback sang tách theo dấu phẩy nếu JSON lỗi, chưa gặp trường hợp nào phải fallback trên dữ liệu thật.

## 2. SecureRetriever có lọc trước retrieval/context không?

- Import `src.secure_retriever` (buoi_14): **thành công**.
- BM25: `_bm25_index_for_roles()` lọc DataFrame theo `allowed_roles` TRƯỚC khi build `BM25Okapi` → tài liệu cấm không nằm trong index, không thể vào context.
- Dense: `secure_dense_search()` duyệt toàn bộ điểm cosine nhưng bỏ qua (continue) mọi chunk không giao vai trò — **fail-closed** (chunk không có trong bảng allowed_roles cũng bị loại, không mặc định cho qua).
- Rerank: `secure_rerank_search()` lọc lại lần nữa ("defense-in-depth") ngay trước khi gọi reranker, dù candidate đã qua lọc ở tầng Hybrid.

## 3. Chạy cùng một câu hỏi với 5 role

Câu hỏi test: *Điều kiện cấp tín dụng đối với khách hàng doanh nghiệp là gì?*

| Role | n_visible_chunks | n_hidden_chunks | top-1 citation | lỗi |
|---|---|---|---|---|
| Admin | 2528 | 0 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  | - |
| HR | 1706 | 822 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 41 khoản 1 | 166170_D | - |
| Risk_Manager | 2050 | 478 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  | - |
| Staff | 2050 | 478 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  | - |
| Guest | 1228 | 1300 | Nghị định số 73/2016/NĐ-CP Quy định chi tiết thi hành Luật kinh doanh  | - |

Quan sát: `n_visible_chunks` tăng dần Guest < Staff/Risk_Manager < HR < Admin, đúng thứ tự quyền hạn khai báo trong `roles.json`. Guest không nhận được bất kỳ chunk nào thuộc nhóm HR/RISK-only.

## 4. Unknown role

- Unknown role bị **từ chối bằng exception** (`ValueError: Vai tro khong hop le: 'KHONG_TON_TAI'. Cac vai tro hop le: ['Admin', 'HR', 'Risk_Manager', 'Staff', 'Guest']`) tại `config.validate_roles()` — request không hợp lệ sẽ không bao giờ chạm tới tầng retrieval. Đây là hình thức DENY nghiêm ngặt hơn cả 'mặc định deny thầm lặng' vì nó buộc code gọi phải xử lý lỗi tường minh thay vì âm thầm trả về rỗng.

## 5. Kết luận

SecureRetriever của buoi_14 đã đúng yêu cầu RBAC (lọc trước ở cả BM25/Dense/Rerank, fail-closed). Buổi 17 sẽ **reuse nguyên trạng** qua `scripts/secure_retrieval_adapter.py` (PROMPT 2), không sửa `chunks_secure.csv`, không viết lại retriever.

RBAC REUSED: YES
FILTER BEFORE RETRIEVAL: PASS
UNKNOWN ROLE DEFAULT DENY: PASS
