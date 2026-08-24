# Vì sao không có `rbac_policy.json` riêng ở đây

Buổi 17 tái sử dụng nguyên trạng RBAC của các buổi trước thay vì tự tạo policy
mới, đúng nguyên tắc "Không tự bịa chính sách phân quyền Agribank; policy
trong bài là mô phỏng":

- Nguồn chân lý duy nhất cho danh sách vai trò và luật phân loại vẫn là
  `../buoi_14/roles.json` (không sao chép sang đây để tránh hai bản dữ liệu
  có thể lệch nhau theo thời gian).
- Dữ liệu phân quyền từng chunk là cột `allowed_roles` trong
  `../buoi_14/data/processed/chunks_secure.csv` (do
  `../buoi_14/scripts/assign_security_tags.py` sinh ra ở Buổi 15).

Xem `outputs/rbac_reuse_report.md` (PROMPT 1) để biết chi tiết việc kiểm tra
và tái sử dụng.
