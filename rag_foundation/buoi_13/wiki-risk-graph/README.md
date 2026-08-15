# Wiki Risk Graph — MVP (Bài thực hành buổi 13)

Wiki tri thức rủi ro dạng đồ thị, dựng từ 4 file CSV mô phỏng (`risk_profiles_seed.csv`,
`controls_seed.csv`, `risk_events_seed.csv`, `relationships_seed.csv`), theo phương pháp
Vibe Coding: chạy từng bước, kiểm tra output thật, không để Agent tự bịa dữ liệu.

> Lưu ý: bộ 4 file CSV trong `data/` là **bộ dữ liệu seed gốc của khóa học** (`data_origin=SYNTHETIC`,
> xem `data/DATA_README_goc.md` và `data/SOURCE.md`) — 12 hồ sơ rủi ro, 10 kiểm soát, 12 sự kiện,
> 22 quan hệ. Không phải số liệu nội bộ Agribank, không dùng `loss_amount_vnd` mô phỏng cho báo
> cáo nghiệp vụ hay kết luận kiểm toán (xem `data/DATA_README_goc.md`).

## Kiến trúc

```
wiki-risk-graph/
├── data/                 # 4 CSV nguồn (mô phỏng)
├── outputs/               # entities.csv, relations.csv, wiki_validation_report.md
├── wiki/                  # Wiki Markdown cho Obsidian (Home.md, risks/, controls/, events/)
├── scripts/                # 5 script Python, chạy tuần tự theo thứ tự bên dưới
├── cypher/                # schema.cypher, demo_queries.cypher (Neo4j)
├── requirements.txt
└── README.md
```

Đồ thị MVP: `KiemSoat -MITIGATES-> RuiRo -OBSERVED_AS-> SuKienRuiRo`

## Thứ tự chạy project

```bash
# (tuỳ chọn) cài driver Neo4j nếu muốn thực hiện Bước 6
pip install -r requirements.txt

# Bước 1 — kiểm tra dữ liệu nguồn
python3 scripts/inspect_data.py

# Bước 2 — chuẩn hoá thành entities.csv / relations.csv
python3 scripts/build_entities.py

# Bước 3 — sinh Wiki Markdown cho Obsidian
python3 scripts/build_wiki.py

# Bước 4 — kiểm thử Wiki (broken link, orphan page, khoảng trống dữ liệu...)
python3 scripts/validate_wiki.py

# Bước 5 — mở bằng Obsidian (thao tác thủ công, xem mục bên dưới)

# Bước 6 — nạp vào Neo4j (cần Neo4j đang chạy + file .env)
python3 scripts/load_neo4j.py
```

## Bước 5 — Mở bằng Obsidian

1. Mở Obsidian trên máy bạn.
2. Chọn **Open folder as vault**.
3. Chọn thư mục `wiki/` (không chọn cả `wiki-risk-graph/`).
4. Mở `Home.md` để bắt đầu.
5. Mở **Graph View** để quan sát cụm `KiemSoat → RuiRo → SuKienRuiRo`.

Câu hỏi quan sát gợi ý: một rủi ro có bao nhiêu kiểm soát? một kiểm soát đang giảm thiểu
rủi ro nào? có node nào đứng một mình (orphan) không — xem thêm trong
`outputs/wiki_validation_report.md`, mục "RuiRo khong co KiemSoat" cho biết trước.

## Bước 6 — Neo4j

Tạo file `.env` tại thư mục gốc project (không commit file này, không hard-code password
trong code):

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<mật khẩu của bạn>
NEO4J_DATABASE=neo4j
```

Sau đó:

```bash
# Áp schema (constraint + index) — chạy trong Neo4j Browser hoặc cypher-shell
cat cypher/schema.cypher

# Nạp dữ liệu (dùng MERGE, chạy lại nhiều lần không tạo duplicate)
python3 scripts/load_neo4j.py

# Demo query A-F
cat cypher/demo_queries.cypher
```

Nếu Neo4j chưa chạy hoặc chưa cấu hình `.env`, `load_neo4j.py` sẽ in hướng dẫn rõ ràng
và thoát an toàn, không ảnh hưởng tới các file Wiki đã tạo ở Bước 1-4.

## Quy tắc dữ liệu (không được vi phạm)

- Không tự bịa quan hệ ngoài `relationships_seed.csv`.
- Không tự đổi `PROPOSED` thành `VERIFIED`.
- Không suy luận tên đơn vị từ `owner_unit_id`, không suy luận tên vai trò từ `owner_role_id`
  (bộ dữ liệu hiện tại chưa có master data `units.csv` / `roles.csv`).
- Nếu thiếu dữ liệu, Wiki hiển thị rõ "Chưa có dữ liệu." thay vì bỏ trống hoặc bịa.

## Kết quả kiểm thử (outputs/wiki_validation_report.md)

- 35 file Markdown, 78 wikilink, 0 broken link, 0 ID trùng, 0 relation tham chiếu sai, 0 orphan page.
- Khoảng trống dữ liệu (không phải lỗi code): `RR-011` và `RR-012` chưa có kiểm soát (KiemSoat)
  nào được ghi nhận trong bộ dữ liệu seed — mọi RuiRo khác đều có đủ 1 kiểm soát và 1 sự kiện.

## Mở rộng sau MVP

Bổ sung `units.csv`, `roles.csv`, `processes.csv`, `documents.csv`, `clauses.csv` để mở
rộng ontology sang `DonVi -OWNS-> RuiRo`, `VaiTro -PERFORMS-> KiemSoat`,
`QuyTrinh -EXPOSES_TO-> RuiRo`, `VanBan -CONTAINS-> DieuKhoan`, `DieuKhoan -REQUIRES-> KiemSoat`,
`VanBan -GOVERNS-> QuyTrinh` — bước chuyển tiếp tự nhiên sang Graph RAG / Multi-hop Reasoning.
