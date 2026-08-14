# Buổi 10 — Chunking HTML phân cấp, Embedding tiếng Việt, nạp Neo4j

> **Không phải tư vấn pháp lý.** Hệ thống chỉ tra cứu và trích dẫn lại nội dung văn
> bản đã nạp. Dữ liệu HTML hiện dùng là **phái sinh từ OCR**, có thể còn lỗi nhận
> dạng — phải đối chiếu văn bản gốc và quy định hiện hành của Agribank / Ngân hàng
> Nhà nước trước khi sử dụng. Không dùng để thay thế thẩm định hoặc ra quyết định
> cấp tín dụng. Không nạp dữ liệu định danh khách hàng hoặc số liệu nội bộ chưa
> công bố vào `data/`, `storage/`, `reports/`.

## Trạng thái hiện tại

| Bước | Trạng thái |
|---|---|
| Sinh HTML đầu vào từ OCR Buổi 05 | **Xong** — `data/raw_html/41_2016_TT_NHNN.html` |
| Bổ sung toàn văn văn bản viện dẫn | **Xong** — `46_2010_QH12.html` (Điều 1–66, đủ), `156_2013_ND_CP.html` (Điều 1–6, đủ), `47_2010_QH12.html` (Điều 1–49/165, MỘT PHẦN — xem ghi chú) |
| Bước 1 — Chunking phân cấp | **Xong, đã chạy thật** — 1.823 chunk (4 văn bản) |
| Bước 2 — Embedding | **Xong, đã chạy thật** — CPU, model `thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5` |
| Bước 3 — Kết nối Neo4j | **Xong, đã chạy thật** — Neo4j Desktop 2.2.1, database `kb-hops` |
| Bước 4 — Nạp đồ thị | **Xong, đã chạy thật** — 1.823 Chunk + 4 Document nạp vào Neo4j |
| Bước 5 — Xác minh | **Xong, đã chạy thật** — `reports/verify_20260813T053930.json`, 4 chỉ tiêu toàn vẹn đều = 0 |
| Unit test | **55/55 pass**, offline hoàn toàn |

Kết quả `verify-load` thật mới nhất (2026-08-13, sau khi nạp thêm 3 văn bản
viện dẫn): `document_count=4` (đề bài yêu cầu 15), `document_relationship_count=3`
(đề bài yêu cầu 8) — đúng dự kiến vì repo chỉ có 4 văn bản nguồn, xem "Lưu ý
quan trọng" bên dưới. `chunk_count=1823` (tăng từ 998 vì đã có nội dung thật
cho 3 văn bản trước đây là node stub rỗng), `orphan_chunks=0`,
`next_cross_parent=0`, `multi_parent_chunks=0`, `chunks_without_embedding=0` —
toàn vẹn đồ thị đạt yêu cầu.

**Lưu ý:** `47_2010_QH12.html` (Luật các TCTD) mới chỉ có Điều 1–49 trong tổng
165 Điều — nguồn công khai miễn phí dừng ở đó, xem `data/doc_relationships.json`
mục `note`. Không dùng file này để tra cứu Điều 50 trở đi.

Kết quả chunking trên Thông tư 41/2016/TT-NHNN:

| Cấp bậc | Chương | Mục | Điều | Khoản | Điểm | Đoạn | Bảng |
|---|---|---|---|---|---|---|---|
| Số lượng | 4 | 5 | 24 | 166 | 226 | 540 | 33 |

Quan hệ `NEXT`: 812. Chunk mồ côi: 0. `chunk_id` trùng: 0.

---

## Việc anh cần làm (theo đúng thứ tự)

### Bước A — Cài Neo4j Desktop

1. Tải tại **neo4j.com/download** → "Neo4j Desktop" → cài như phần mềm Windows thường.
2. Mở app → tạo project → **"Add" → "Local DBMS"**.
3. Đặt tên (ví dụ `kb-hops-dbms`) và **đặt mật khẩu** — nhớ mật khẩu này.
4. Bấm **Start**, chờ trạng thái "Active" (chấm xanh).

### Bước B — Tạo database `kb-hops`

Bấm **"Open"** để mở Neo4j Browser, rồi chạy nội dung file `setup_neo4j.cypher`
(mở file đó ra, copy từng lệnh vào Browser). Lệnh chính:

```cypher
CREATE DATABASE `kb-hops` IF NOT EXISTS;
SHOW DATABASES;   // xác nhận kb-hops đang online
```

> **Lưu ý về phiên bản Neo4j.** `CREATE DATABASE` là tính năng **chỉ có trên
> Enterprise Edition** — Community Edition chỉ cho phép đúng một database
> (`neo4j`). May mắn là **Neo4j Desktop đi kèm sẵn Developer License của
> Enterprise** (dùng cá nhân, một máy), nên cài qua Desktop thì lệnh trên chạy
> được bình thường.
>
> Nếu anh cài Neo4j Community server đứng riêng và gặp lỗi `Unsupported
> administration command`, dùng **Phương án B** trong `setup_neo4j.cypher`: bỏ
> qua bước tạo database và sửa `.env` thành `NEO4J_DATABASE=neo4j`.

### Bước C — Cài môi trường Python

```powershell
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_10
python -m venv .venv
.venv\Scripts\activate

# BẮT BUỘC chạy dòng này TRƯỚC — cài torch bản CPU
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Trong `.env`, điền `NEO4J_PASSWORD=` bằng mật khẩu ở Bước A.3.

> **Đừng chạy thẳng `pip install torch`.** Bản mặc định trên PyPI là bản GPU và
> sẽ tải khoảng **3 GB** thư viện CUDA (nvidia-cudnn 366 MB, nvidia-nccl 206 MB,
> cusparselt 170 MB...) mà máy không có GPU không hề dùng đến. Đây là lỗi tôi đã
> gặp thật khi thử cài. Dùng đúng `--index-url .../whl/cpu` như trên.
>
> Kiểm tra đã đúng bản CPU: `python -c "import torch; print(torch.__version__)"`
> — kết quả phải có hậu tố `+cpu`.

### Bước D — Kiểm tra kết nối trước khi nạp

```powershell
python check_connection.py
```

Script này chạy vài giây, không ghi gì. Nếu báo "KẾT NỐI THÀNH CÔNG" thì Bước E
sẽ không fail vì lý do kết nối. Nếu lỗi, script in sẵn danh sách 4 điểm cần kiểm tra.

### Bước E — Chạy pipeline

```powershell
# Bước 1: chỉ parse + in mẫu ra console (không cần Neo4j, không cần model)
python -m src.pipeline parse --input data\raw_html --sample 25

# Bước 2: parse + embed (lần đầu tải model ~vài trăm MB, chạy CPU)
python -m src.pipeline embed --input data\raw_html

# Bước 3+4: nạp toàn bộ đồ thị vào Neo4j
python -m src.pipeline load --input data\raw_html

# Bước 5: xác minh
python -m src.pipeline verify-load
```

Chạy lần lượt, đừng nhảy thẳng lên `load`. Nếu bước `parse` in ra cấu trúc sai,
sửa `src/html_parser.py` trước — đỡ phải xoá dữ liệu đã nạp nhầm.

### Bước F — Kiểm tra trong Neo4j Browser

Chuyển sang database `kb-hops` (dropdown góc trên), rồi:

```cypher
// Các văn bản đã nạp
MATCH (d:Document) RETURN d.doc_id, d.doc_type, d.title;

// Quan hệ giữa các văn bản
MATCH (a:Document)-[r]->(b:Document) RETURN a.doc_id, type(r), b.doc_id;

// Cây phân cấp của Điều 6
MATCH path = (c:Chunk)-[:PARENT_OF*0..3]->(x:Chunk)
WHERE c.heading STARTS WITH 'Điều 6.'
RETURN path LIMIT 50;

// Đếm chunk theo cấp bậc
MATCH (c:Chunk) RETURN c.level, count(*) ORDER BY count(*) DESC;
```

---

## Lưu ý quan trọng về số liệu nghiệm thu

Đề bài yêu cầu **15 Document** và **8 quan hệ liên Document**. Dữ liệu hiện có
trong repo chỉ cho ra **4 Document** (1 toàn văn + 3 văn bản viện dẫn) và
**3 quan hệ `CAN_CU`**, vì repo chỉ có duy nhất 1 văn bản nguồn.

`verify-load` sẽ in cảnh báo `[LỆCH]` — đây là hành vi đúng, không phải lỗi.
Muốn đạt đúng 15/8, cần bổ sung đủ 15 file HTML văn bản luật vào `data/raw_html/`
và khai báo đủ 8 quan hệ trong `data/doc_relationships.json`. Code không cần sửa.

## Chạy test (offline, không cần Neo4j, không cần model)

```powershell
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG
python -m unittest discover -s rag_foundation\buoi_10\tests -t rag_foundation\buoi_10
```

## Sinh lại HTML đầu vào (nếu cần)

```powershell
python -m src.md_to_html --raw ..\buoi_05\output\raw\2026-08-01_TaiLieu_NHNNSigned.json
```

Chỉ đọc từ Buổi 05, không ghi gì vào thư mục Buổi 05.

## Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `check_connection.py` báo password trống | Chưa sửa `.env` | Mở `.env`, điền `NEO4J_PASSWORD` |
| Không kết nối được Neo4j | Instance chưa Start / chưa tạo `kb-hops` / sai mật khẩu | Làm lại Bước A, B, D — `check_connection.py` tự chẩn đoán và in hướng xử lý |
| `Unsupported administration command: CREATE DATABASE` | Đang dùng Community Edition | Phương án B: `NEO4J_DATABASE=neo4j` trong `.env` |
| `Database does not exist` | Chưa chạy `setup_neo4j.cypher` | Làm Bước B |
| pip tải hàng GB `nvidia-*` | Cài nhầm torch bản GPU | Gỡ rồi cài lại bằng `--index-url https://download.pytorch.org/whl/cpu` |
| `ModuleNotFoundError: No module named 'sentence_transformers'` | Chưa cài requirements | `pip install -r requirements.txt` |
| `[CẢNH BÁO] ... chunk dài, có thể bị cắt ở 512 token` | Bảng biểu dài quá giới hạn model | Bình thường với 11 chunk bảng; nếu cần chính xác tuyệt đối cho bảng thì phải chia nhỏ bảng trước khi nhúng |
| `[LỆCH] document_count=4, kỳ vọng 15` | Chỉ có 1 văn bản nguồn | Xem mục "Lưu ý quan trọng" ở trên |
| `[CẢNH BÁO] không có meta doc-id` | HTML tự cung cấp thiếu thẻ meta | Thêm `<meta name="doc-id" content="số hiệu VB">` vào `<head>` |
| Tải model chậm lần đầu | Tải từ HuggingFace | Bình thường, lần sau lấy từ cache |
