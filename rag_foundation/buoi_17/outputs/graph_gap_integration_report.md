# Buổi 17 — Graph / Gap Integration Report (PROMPT 8)

## 1. Kết nối Neo4j thật (từ môi trường chạy script này)

- Cấu hình .env đầy đủ (URI/USER/PASSWORD): True (Neo4j san sang)
- Thử `driver.verify_connectivity()`: THÀNH CÔNG

**Lưu ý quan trọng**: script này đang chạy trong sandbox trên cloud, KHÔNG phải trên máy Windows của học viên — nơi Neo4j Desktop (instance `rag2026`) thực sự đang chạy ở `127.0.0.1:7687`. Từ sandbox này, `127.0.0.1` không trỏ tới máy học viên nên kết nối chắc chắn thất bại — đây là giới hạn môi trường thực thi, KHÔNG phải kết luận rằng Neo4j của học viên có vấn đề. Học viên nên chạy lại đúng script này (`python scripts/graph_gap_integration_check.py`) trên máy của mình, có Neo4j Desktop đang mở, để có kết quả sống thật.

## 2. Quan hệ (relationship) THỰC SỰ được pipeline này tạo ra (đọc tĩnh source code)

- File kiểm tra: `schema.cypher`, `load_secure_kg.py` (buoi_14)
- Relationship type tìm thấy: ['CONTAINS', 'NEXT']
- `load_secure_kg.py` (Buổi 15) CHỈ tạo `(:VanBan)-[:CONTAINS]->(:DieuKhoan)` — quan hệ cấu trúc nội bộ một văn bản (văn bản chứa điều khoản của chính nó), KHÔNG có quan hệ nối giữa văn bản NÀY với văn bản KHÁC (không có kiểu như 'CĂN_CỨ', 'SỬA_ĐỔI', 'HƯỚNG_DẪN' giữa hai văn bản pháp luật khác nhau, hay giữa văn bản bên ngoài và quy định nội bộ).

## 3. Đánh giá theo đúng khung của bài

- Relation chỉ là CONTAINS/NEXT (không giúp): **CONTAINS** — đúng vậy, chỉ nối văn bản với chính điều khoản của nó.
- Relation giúp nối văn bản/điều khoản KHÁC NHAU (Thông tư ↔ quy định nội bộ Agribank): **không có** trong pipeline hiện tại.
- Relation không liên quan: n/a (không có relation nào khác được tạo).

## Kết luận

Ngay cả nếu kết nối Neo4j thành công, quan hệ duy nhất mà pipeline này từng tạo (`CONTAINS`) không nối văn bản bên ngoài với quy định nội bộ — nên KHÔNG có candidate expansion nào hữu ích cho Compliance Gap Checker để bổ sung. Việc thêm graph candidate expansion vào `compliance_gap.py` sẽ là suy diễn, không phải dựa trên dữ liệu graph thật.

GRAPH USED: NO
Lý do: (1) Neo4j không thể kết nối từ môi trường sandbox chạy script này (giới hạn thực thi, cần chạy lại trên máy học viên để xác nhận sống); (2) quan hệ graph duy nhất mà pipeline buoi_14/15 từng tạo ra (CONTAINS) là quan hệ cấu trúc nội bộ một văn bản, không nối được văn bản bên ngoài với quy định nội bộ — không có giá trị bổ sung cho Gap Checker cho dù Neo4j có kết nối được hay không.
