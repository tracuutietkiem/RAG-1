# Review Buổi 10 — Đối chiếu code với buoi_10.md và SPEC_buoi_10.md

**Cách kiểm tra:** Sandbox thực thi (bash) bị lỗi suốt phiên làm việc này
("VM service not running") nên phần soát logic ở mục 2 là đọc mã nguồn thủ
công (truy vết thuật toán bằng tay qua fixture) + đối chiếu số liệu trong
`data/raw_html/41_2016_TT_NHNN.html` bằng tìm kiếm văn bản, không chạy trình
thông dịch. Đã ghi log lỗi môi trường vào `loi_moi_truong_2026-08-12.txt` ở
thư mục gốc.

**Xác nhận thật trên máy anh (2026-08-12):** anh đã tự chạy lệnh ở mục 5 —
kết quả **`Ran 55 tests in 0.046s` → `OK`, 55/55 PASS**. Soát tĩnh và chạy thật
khớp nhau.

**Đã chạy thật TOÀN BỘ pipeline end-to-end (2026-08-12, 20:56):** dùng script
`chay_buoi_10.ps1` (mục 7) — parse → embed (CPU) → nạp Neo4j `kb-hops` →
verify-load. Kết quả `reports/verify_20260812T205614.json`:

```json
{
  "document_count": 4,
  "document_relationship_count": 3,
  "chunk_count": 998,
  "orphan_chunks": 0,
  "next_cross_parent": 0,
  "multi_parent_chunks": 0,
  "chunks_without_embedding": 0
}
```

4 chỉ tiêu toàn vẹn đều bằng 0 — đúng invariant đã soát tĩnh ở mục 2.
`document_count=4`/`document_relationship_count=3` là đúng dự kiến (không phải
lỗi), xem mục 8.

## 1. Đối chiếu 5 bước của đề bài (`buoi_10.md`)

| Bước đề bài | Trạng thái code | Ghi chú |
|---|---|---|
| B1: làm sạch HTML + chunk cha–con, in mẫu console | ĐÚNG | `html_parser.py` + `print_sample()`; đã chạy thật, 998 chunk trên Thông tư 41 |
| B2: embedding model tiếng Việt, CPU-only | ĐÚNG | `embedding.py`; `EmbeddingConfig.from_env()` chặn cứng nếu `EMBEDDING_DEVICE != cpu`; model/import torch chỉ lazy-load khi thật sự nhúng |
| B3: cấu hình kết nối Neo4j (7687/7474) | ĐÚNG | `.env.example` đúng 2 cổng; `check_connection.py` chẩn đoán 4 loại lỗi kết nối thường gặp |
| B4: nạp Document/Chunk + PART_OF/PARENT_OF/NEXT/CAN_CU-THAY_THE-HOP_NHAT | ĐÚNG | `neo4j_loader.py`; toàn bộ ghi dùng `MERGE` trên khoá nghiệp vụ → idempotent |
| B5: kiểm tra Neo4j Browser, đếm Document/quan hệ | ĐÚNG (có cảnh báo trung thực) | `verify-load` in `[LỆCH]` vì dữ liệu hiện có chỉ 4 Document/3 quan hệ, không phải 15/8 như đề bài giả định — đã giải thích rõ trong SPEC mục 8, không bịa số cho khớp |

Toàn bộ 5 bước đề bài đều có code tương ứng và đúng schema Neo4j đã khai
(`Document`, `Chunk`, `PART_OF`, `PARENT_OF`, `NEXT`, `CAN_CU`).

## 2. Soát logic chi tiết (không tìm thấy lỗi)

- **Nhận diện heading** (`classify_level`): "Điều N." bắt buộc có dấu chấm và
  neo đầu block → không bắt nhầm câu tham chiếu giữa văn bản (đã verify lại
  bằng fixture `Chương II... "tham chiếu quy định tại Điều 1 nêu trên"` → đúng
  thành `doan`, không thành heading).
- **Khoản/Điểm chỉ được nhận trong phạm vi Điều** (`inside_dieu`) — tránh nhận
  nhầm các dòng "1." / "a)" ở phần mở đầu hay phụ lục.
- **Cây phân cấp** (`build_hierarchy`): thuật toán stack theo `LEVEL_ORDER`
  đóng đúng các heading con khi gặp heading cùng cấp/cao hơn; đã truy vết tay
  qua fixture `tests/fixtures/sample_law.html` ra đúng cấu trúc 2 Chương → mỗi
  Chương có Điều con → đoạn/bảng là lá.
- **`chunk_id` ổn định** (hash `doc_id + path cấp bậc`) → nạp lại không sinh
  trùng, khớp yêu cầu idempotent của SPEC mục 5.
- **`compute_next_links`**: chỉ nối `NEXT` giữa các chunk có cùng `parent_id`,
  sắp theo `order_index` — đúng ràng buộc "chỉ nối anh em cùng cha".
- **Truy vấn `verify_load`**: đã đọc kỹ từng Cypher trong `VERIFY_QUERIES`.
  - `orphan_chunks`: đúng — chunk vừa không có `PART_OF` tới Document vừa
    không có `PARENT_OF` trỏ vào thì mới tính là mồ côi.
  - `next_cross_parent`: đúng — loại trừ cả hai trường hợp hợp lệ (chung cha
    là Chunk, hoặc cả hai đều là chunk gốc không cha nào).
  - Test `test_verify_load_is_read_only` khoá đúng: không cho phép
    `MERGE/CREATE/DELETE/SET/REMOVE` lọt vào các câu verify.
- **`md_to_html.py`**: regex số hiệu văn bản `\d+/\d{4}/[A-ZĐ][A-Z0-9Đ\-]*` đã
  sửa đúng lỗi `\b` không khớp giữa chữ và số (ví dụ "QH12") — có test khoá lại
  lỗi này (`test_extracts_three_can_cu_references`).
- **Bảo mật**: `check_connection.py` không in giá trị `NEO4J_PASSWORD`, chỉ
  báo "đã điền/trống". `.env.example` không chứa mật khẩu thật. `.gitignore`
  loại trừ `.env`. Không thấy chỗ nào log secret.

## 3. Đối chiếu số liệu đã công bố với dữ liệu thật (bằng tìm kiếm văn bản)

| Chỉ tiêu | README/SPEC công bố | Đếm lại trong `41_2016_TT_NHNN.html` | Khớp |
|---|---|---|---|
| Chương | 4 | 4 (`<h1>Chương...`) | ✅ |
| Mục | 5 | 5 (`Mục 1..5`, các heading level h1–h3 khác nhau) | ✅ |
| Điều | 24 | 24 (`Điều N.`) | ✅ |
| Bảng | 33 | 33 (`<table>`) | ✅ |

Không phát hiện sai lệch số liệu đã báo cáo trong README/SPEC so với file HTML
thực tế.

## 4. Lỗi đã sửa trong lần review này

1. **SPEC_buoi_10.md dòng 7** ghi "51 unit test pass" trong khi README và số
   test đếm thủ công trong `tests/` ra đúng **55** (14 + 5 + 15 + 11 + 10 theo
   từng file test) — khớp với README. Đã sửa SPEC thành 55.
2. **`lxml` không cài được trên Python 3.14 (máy anh)** — không có wheel dựng
   sẵn cho `cp314` trên Windows, pip phải biên dịch từ mã nguồn và đòi hỏi
   Microsoft C++ Build Tools (không nên bắt học viên cài chỉ để chạy bài thực
   hành). Sửa: đổi `html_parser.py` sang dùng `html.parser` (built-in Python,
   không cần biên dịch) thay `lxml`; bỏ `lxml` khỏi `requirements.txt`.
3. **`check_connection.py` crash `UnicodeEncodeError` khi in tiếng Việt có
   dấu** — do output bị pipe qua `Tee-Object` trong `chay_buoi_10.ps1` nên
   Python không còn thấy console thật, rơi về bảng mã cp1252 của hệ thống thay
   vì UTF-8. Sửa: đặt `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` trong
   `chay_buoi_10.ps1` trước khi gọi mọi lệnh Python.
4. **`chay_buoi_10.ps1` dừng nhầm ở bước dò torch** — ban đầu để
   `$ErrorActionPreference = "Stop"`, khiến PowerShell coi traceback bình
   thường (khi dò xem torch đã cài chưa) là lỗi nghiêm trọng và thoát ngay.
   Sửa: đổi thành `"Continue"` và tự kiểm soát lỗi bằng `$LASTEXITCODE` ở từng
   bước.

Không tìm thấy lỗi logic nghiệp vụ nào khác cần sửa trong `src/` — 3 lỗi #2–#4
đều là lỗi môi trường chạy trên Windows/Python 3.14, không phải lỗi thuật
toán chunking/embedding/Neo4j.

## 5. Việc anh cần tự làm để có xác nhận thật (không phải lỗi code)

Vì sandbox không chạy được Python trong phiên này, đề nghị anh tự chạy trên máy
để có kết quả PASS/FAIL thật, theo đúng README:

```powershell
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG
python -m unittest discover -s rag_foundation\buoi_10\tests -t rag_foundation\buoi_10
```

Nếu ra khác 55/55 PASS, gửi lại log để tôi sửa tiếp — phần soát tĩnh không thay
thế được việc chạy thật.

## 7. Script tự động `chay_buoi_10.ps1`

Để chạy hết Bước C→F trong 1 lệnh, đã thêm `chay_buoi_10.ps1` — tự tạo `.venv`,
cài torch bản CPU đúng cách, cài `requirements.txt`, mở `.env` cho anh điền mật
khẩu Neo4j, rồi chạy tuần tự `parse → embed → load → verify-load`, ghi log ra
`reports/chay_<timestamp>.log` và dừng kèm hướng dẫn cụ thể nếu có bước lỗi.
Trong quá trình chạy thật đã bắt và sửa 3 lỗi môi trường (mục 4, #2–#4) và hỗ
trợ trực tiếp trên màn hình anh (qua công cụ điều khiển máy tính) để tạo
database `kb-hops` trong Neo4j Desktop khi `check_connection.py` báo "connection
refused" — DBMS lúc đó đang chạy nhưng chưa có database nào (kể cả `neo4j` mặc
định); vào thẳng Neo4j Desktop → Query, chạy `:use system` rồi
`CREATE DATABASE \`kb-hops\` IF NOT EXISTS` là xong, không cần sửa code.

## 8. Giới hạn đã biết, không phải lỗi mới

- `document_count`/`document_relationship_count` hiện là 4/3, chưa đạt 15/8 đề
  bài giả định — do repo chỉ có 1 văn bản luật nguồn (Thông tư 41). Đây là giới
  hạn dữ liệu đầu vào, không phải lỗi code; SPEC/README đã nói rõ và
  `verify-load` tự báo `[LỆCH]` trung thực thay vì bịa số.
- HTML đầu vào là dữ liệu phái sinh từ OCR Buổi 05, có thể còn lỗi nhận dạng —
  phải đối chiếu văn bản gốc trước khi dùng cho công việc nghiệp vụ thật, đúng
  ghi chú "Không phải tư vấn pháp lý" ở đầu README.
