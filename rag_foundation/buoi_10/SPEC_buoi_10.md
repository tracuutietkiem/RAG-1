# SPEC — Buổi 10: Chunking phân cấp HTML, Embedding tiếng Việt và nạp Neo4j

Tài liệu quy chiếu bắt buộc cho toàn bộ Buổi 10. Mọi prompt/code tiếp theo phải đọc
file này trước khi sửa. Đề bài gốc: `../../../buoi_10.md` (không sửa file đó).

> **Trạng thái (đã cập nhật 2026-08-12):** Toàn bộ 5 bước đã chạy thật trên máy
> người dùng, end-to-end: 998 chunk → nhúng CPU → nạp Neo4j (`kb-hops`) →
> verify-load. Kết quả `reports/verify_20260812T205614.json`:
> `document_count=4, document_relationship_count=3, chunk_count=998,
> orphan_chunks=0, next_cross_parent=0, multi_parent_chunks=0,
> chunks_without_embedding=0`. 4/3 là đúng dự kiến (xem mục 8) vì repo chỉ có
> 1 văn bản nguồn — không phải lỗi. 55/55 unit test pass (offline).

---

## 1. Mục tiêu và khác biệt so với Buổi 05–09

Buổi 05–09 lưu chunk trong ChromaDB (vector store phẳng, quan hệ cha–con mô phỏng
bằng JSON registry ở Buổi 09). Buổi 10 chuyển **nguồn sự thật** của cấu trúc phân
cấp sang một cơ sở dữ liệu đồ thị thật (Neo4j), để quan hệ Cha–Con và quan hệ giữa
các văn bản (căn cứ, thay thế, hợp nhất) trở thành cạnh (edge) tường minh, truy vấn
được bằng Cypher — không còn phải tự dựng registry JSON như Buổi 09.

| Buổi 09 | Buổi 10 |
|---|---|
| Hierarchy registry là JSON tự dựng (`children.json`/`parents.json`) | Hierarchy là đồ thị thật trong Neo4j (`PARENT_OF`) |
| Input: chunk đã có sẵn từ Buổi 05 (PDF → OCR → text) | Input: văn bản luật dạng **HTML** |
| Không có quan hệ giữa các Document | Có quan hệ cấp tài liệu: `CAN_CU`, `THAY_THE`, `HOP_NHAT` |
| Embedding: Gemini Embedding API (cloud) | Embedding: model HuggingFace tiếng Việt, chạy **CPU cục bộ** |
| Lưu trữ: ChromaDB local | Lưu trữ: Neo4j local (`kb-hops`) |

Buổi 10 **không** thay thế Buổi 05–09 và không sửa bất kỳ file nào trong các thư mục
đó. Đây là một nhánh xử lý dữ liệu song song, dùng nguồn HTML thay vì PDF.

---

## 2. Sơ đồ pipeline

```
Thư mục HTML luật (data/raw_html/*.html)
        │
        ▼
Bước 1 — HTML cleaner + hierarchical chunker (src/html_parser.py)
        │   Làm sạch HTML giữ heading/đoạn/bảng
        │   Cây: Document → Chương → Mục → Điều → đoạn/bảng
        │   In console mẫu 1 văn bản để minh hoạ (yêu cầu bắt buộc của đề bài)
        ▼
Bước 2 — Embedding (src/embedding.py)
        │   Model: thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5
        │   Bắt buộc CPU (torch-cpu), KHÔNG yêu cầu GPU
        ▼
Bước 3 — Kết nối Neo4j (src/neo4j_loader.py)
        │   Bolt: 7687, HTTP Browser: 7474, database: kb-hops
        ▼
Bước 4 — Nạp đồ thị (src/neo4j_loader.py)
        │   (:Document)-[:PART_OF]-(:Chunk)
        │   (:Chunk)-[:PARENT_OF]->(:Chunk con)
        │   (:Chunk)-[:NEXT]->(:Chunk anh em kế tiếp)
        │   (:Document)-[:CAN_CU|:THAY_THE|:HOP_NHAT]->(:Document)
        ▼
Bước 5 — Kiểm tra và xác minh (src/pipeline.py verify-load)
        Đếm (:Document) = 15, đếm quan hệ liên Document = 8 (theo đề bài)
```

---

## 3. Cấu trúc project

```
rag_foundation/buoi_10/
├── SPEC_buoi_10.md          ← file này
├── README.md                 hướng dẫn chạy, cài đặt, biến môi trường
├── requirements.txt
├── .env.example               không commit .env thật (chứa mật khẩu Neo4j)
├── setup_neo4j.cypher         lệnh tạo database kb-hops + constraint
├── check_connection.py         kiểm tra kết nối Neo4j trước khi nạp
├── data/
│   ├── raw_html/               HTML đầu vào (đã sinh 41_2016_TT_NHNN.html)
│   └── doc_relationships.json  khai báo Document stub + quan hệ liên văn bản
├── src/
│   ├── __init__.py
│   ├── md_to_html.py          cầu nối: OCR Buổi 05 → HTML (xem mục 4)
│   ├── html_parser.py         Bước 1 — làm sạch + chunk phân cấp
│   ├── embedding.py            Bước 2 — nhúng vector CPU
│   ├── neo4j_loader.py         Bước 3–4 — kết nối + nạp đồ thị
│   └── pipeline.py             CLI orchestration + Bước 5 verify
├── tests/                      51 unit test, offline hoàn toàn
│   ├── fixtures/                HTML mẫu nhỏ tự viết
│   ├── test_html_parser.py
│   ├── test_md_to_html.py
│   ├── test_embedding.py
│   ├── test_neo4j_loader.py     dùng FakeSession, không cần Neo4j thật
│   └── test_pipeline_integration.py
├── storage/                    cache trung gian (tuỳ chọn)
└── reports/                    kết quả verify-load (JSON), không chứa dữ liệu KH
```

---

## 4. Nguồn dữ liệu HTML — đã giải quyết bằng cầu nối từ Buổi 05

Repo không có sẵn file HTML nào. PDF gốc `2026-08-01_TaiLieu_NHNNSigned.pdf`
(Thông tư 41/2016/TT-NHNN) có lớp text **hỏng nặng**, mất dấu tiếng Việt:

```
Di~u 1.Ph~m vi di~u chinh va dBi tUQ'ngap dVng      ← text layer của PDF gốc
Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng      ← bản OCR sạch của Buổi 05
```

Vì vậy `src/md_to_html.py` sinh HTML từ **kết quả OCR đã sạch của Buổi 05**
(`buoi_05/output/raw/*.json`), chỉ đọc, không ghi gì vào thư mục Buổi 05.

```powershell
python -m src.md_to_html --raw ..\buoi_05\output\raw\2026-08-01_TaiLieu_NHNNSigned.json
```

Kết quả thực tế đã chạy:

| Đầu ra | Nội dung |
|---|---|
| `data/raw_html/41_2016_TT_NHNN.html` | Toàn văn Thông tư 41/2016/TT-NHNN (~227 KB) |
| `data/doc_relationships.json` | 1 văn bản chính + 3 văn bản viện dẫn + 3 quan hệ `CAN_CU` |

Ba quan hệ `CAN_CU` được rút từ chính phần mở đầu văn bản (không phải số liệu tự
đặt): Luật 46/2010/QH12, Luật 47/2010/QH12, Nghị định 156/2013/NĐ-CP.

> **Giới hạn phải nói rõ:** HTML này là dữ liệu **phái sinh từ OCR**, có thể còn
> lỗi nhận dạng (ví dụ dòng đầu vẫn là "NGAN HÀNG" thiếu dấu). Mọi trích dẫn về
> sau phải đối chiếu văn bản gốc trước khi dùng cho công việc.

Nếu anh có bộ HTML văn bản luật thật (đủ 15 văn bản như đề bài giả định), chỉ cần
copy vào `data/raw_html/` và khai báo quan hệ trong `data/doc_relationships.json`
là chạy được ngay, không cần sửa code.

---

## 5. Schema đồ thị Neo4j (bắt buộc theo đề bài)

**Node `(:Document)`**

```
{
  doc_id: string (khoá nghiệp vụ, ví dụ số hiệu văn bản — duy nhất, có constraint),
  title: string,
  doc_type: string,           // Luật | Nghị định | Thông tư | Quyết định...
  issue_number: string | null,
  issue_date: date | null,
  effective_date: date | null,
  source_file: string,        // tên file HTML gốc
  ingested_at: datetime
}
```

**Node `(:Chunk)`**

```
{
  chunk_id: string (duy nhất, ổn định — hash từ doc_id + đường dẫn cấp bậc),
  level: string,               // chuong | muc | dieu | doan | bang
  heading: string | null,
  text: string,                // nội dung đã làm sạch, không còn thẻ HTML
  order_index: int,            // thứ tự đọc trong văn bản cha
  embedding: float[],           // vector nhúng
  embedding_model: string,
  embedding_dim: int
}
```

**Quan hệ bắt buộc**

| Quan hệ | Chiều | Ý nghĩa |
|---|---|---|
| `[:PART_OF]` | `(:Chunk)-[:PART_OF]->(:Document)` | Chunk gốc thuộc văn bản nào |
| `[:PARENT_OF]` | `(:Chunk cha)-[:PARENT_OF]->(:Chunk con)` | Cấu trúc phân cấp Chương→Mục→Điều→đoạn |
| `[:NEXT]` | `(:Chunk)-[:NEXT]->(:Chunk anh em kế tiếp)` | Giữ thứ tự đọc giữa các chunk **cùng cấp, cùng cha** |
| `[:CAN_CU]` | `(:Document)-[:CAN_CU]->(:Document)` | Văn bản này căn cứ vào văn bản kia |
| `[:THAY_THE]` | `(:Document)-[:THAY_THE]->(:Document)` | Văn bản này thay thế văn bản kia |
| `[:HOP_NHAT]` | `(:Document)-[:HOP_NHAT]->(:Document)` | Văn bản hợp nhất từ nhiều văn bản |

Ràng buộc bắt buộc khi nạp:

- `doc_id` và `chunk_id` phải có **uniqueness constraint** trong Neo4j (tạo bằng
  Cypher `CREATE CONSTRAINT`), tránh nạp trùng khi chạy lại.
- Mỗi `Chunk` gốc (`level="chuong"` hoặc cấp cao nhất) phải nối `[:PART_OF]` thẳng
  tới `(:Document)` bằng tiêu đề tương ứng — đúng yêu cầu đề bài, không chỉ nối qua
  chuỗi `PARENT_OF` rồi suy ra.
- `[:NEXT]` chỉ nối giữa **anh em liền kề cùng cha**, không nối chéo cấp.
- Nạp phải **idempotent**: chạy lại với cùng input không tạo node/quan hệ trùng —
  dùng `MERGE`, không dùng `CREATE` thô cho node có khoá nghiệp vụ.

---

## 6. Biến môi trường (`.env`, xem `.env.example`)

```ini
NEO4J_URI=bolt://localhost:7687
NEO4J_HTTP_URI=http://localhost:7474
NEO4J_USER=neo4j
NEO4J_PASSWORD=                     # KHÔNG commit giá trị thật
NEO4J_DATABASE=kb-hops

EMBEDDING_MODEL=thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5
EMBEDDING_DEVICE=cpu                # bắt buộc cpu theo đề bài, không đổi sang cuda ở máy không GPU
EMBEDDING_BATCH_SIZE=16

HTML_INPUT_DIR=data/raw_html
CHUNK_PRINT_SAMPLE=true             # bắt buộc in mẫu ra console (yêu cầu đề bài Bước 1)
```

**Không commit `.env` thật lên git** (đã có `.gitignore`). Không đưa mật khẩu Neo4j,
số liệu khách hàng hay dữ liệu nội bộ chưa công bố vào bất kỳ file nào trong
`data/`, `storage/`, `reports/` — theo đúng nguyên tắc bảo mật đã thống nhất.

---

## 7. Testability và dependency injection

Theo đúng phong cách các buổi trước — mọi thành phần chạm mạng/model đều phải
tiêm được fake để unit test chạy **offline, không cần Neo4j thật, không tải model
thật**:

- `html_parser.py`: hàm thuần (input string HTML → output list chunk), không I/O
  ngoài đọc file → dễ test trực tiếp với fixture nhỏ.
- `embedding.py`: `embed_fn` injectable; test dùng fake trả vector cố định chiều
  384 (chiều thực tế của model phải xác nhận khi chạy lần đầu, cập nhật lại SPEC
  nếu khác).
- `neo4j_loader.py`: `driver_factory` injectable; test dùng `FakeSession`/
  `FakeTransaction` ghi lại các câu Cypher đã "chạy" để assert, không mở kết nối
  mạng thật trong test.
- `pipeline.py` (CLI): mỗi bước gọi được độc lập (`parse`, `embed`, `load`,
  `verify-load`) để debug từng khâu mà không phải chạy lại toàn bộ.

---

## 8. Tiêu chí nghiệm thu (Bước 5 của đề bài)

Lệnh `python -m src.pipeline verify-load` chạy 7 truy vấn **chỉ đọc**, in JSON,
lưu báo cáo vào `reports/verify_<timestamp>.json`, rồi đối chiếu từng chỉ tiêu:

| Chỉ tiêu | Ý nghĩa | Ngưỡng |
|---|---|---|
| `document_count` | Số node `(:Document)` | = 15 (đề bài) |
| `document_relationship_count` | Quan hệ `CAN_CU`/`THAY_THE`/`HOP_NHAT` | = 8 (đề bài) |
| `chunk_count` | Số node `(:Chunk)` | > 0 |
| `orphan_chunks` | Chunk không nối được về Document và không có cha | = 0 |
| `next_cross_parent` | Quan hệ `NEXT` nối hai chunk khác cha | = 0 |
| `multi_parent_chunks` | Chunk có nhiều hơn một cha | = 0 |
| `chunks_without_embedding` | Chunk thiếu vector nhúng | = 0 |

Bốn chỉ tiêu toàn vẹn cuối bảo vệ các invariant ở mục 5. Có unit test khoá lại
việc `verify_load` không được chứa `MERGE`/`CREATE`/`DELETE`/`SET`/`REMOVE`.

**Đề bài yêu cầu 15 Document và 8 quan hệ liên Document. Dữ liệu hiện có KHÔNG
đạt được con số đó** — và điều này phải được nói thẳng, không "làm tròn":

| Chỉ tiêu | Đề bài | Dữ liệu thực tế hiện có | Chênh lệch do |
|---|---|---|---|
| `document_count` | 15 | **4** (1 toàn văn + 3 stub viện dẫn) | Chỉ có 1 văn bản nguồn trong repo |
| `document_relationship_count` | 8 | **3** (đều là `CAN_CU`) | Thông tư 41 chỉ viện dẫn 3 văn bản |
| `chunk_count` | > 0 | **998** | — |
| `orphan_chunks` | 0 | 0 (đã kiểm tra ở tầng parser) | — |

`verify-load` in cảnh báo `[LỆCH]` khi số đếm khác 15/8 nhưng **không tự bịa thêm
node** để cho khớp. Muốn đạt đúng 15/8, cần bổ sung đủ 15 văn bản HTML thật vào
`data/raw_html/` và khai báo đủ 8 quan hệ trong `data/doc_relationships.json`.

Số liệu Bước 1 đã kiểm chứng trên dữ liệu thật (998 chunk):

| Cấp bậc | Số lượng |
|---|---|
| Chương | 4 |
| Mục | 5 |
| Điều | 24 |
| Khoản | 166 |
| Điểm | 226 |
| Đoạn | 540 |
| Bảng | 33 |
| Quan hệ `NEXT` | 812 |
| Chunk mang cảnh báo `document_fallback` | 19 (phần mở đầu, trước Chương I) |

---

## 9. Phạm vi ghi

Chỉ ghi trong `rag_foundation/buoi_10/`. Không sửa code/dữ liệu/storage của
Buổi 05–09. Không commit `.env`, không commit dữ liệu HTML thật nếu chứa thông
tin nội bộ chưa công bố.

## 10. Việc còn lại phải làm trên máy người dùng

Ba việc sau bắt buộc chạy tại máy local, không thực hiện từ xa được:

1. Cài **Neo4j Desktop 2.0**, tạo local DBMS, start instance, chạy
   `setup_neo4j.cypher` để tạo database `kb-hops`.
2. Copy `.env.example` → `.env`, điền `NEO4J_PASSWORD` thật, rồi chạy
   `python check_connection.py` để xác nhận kết nối trước khi nạp.
3. Cài torch **bản CPU** trước, rồi mới `pip install -r requirements.txt`.
   Chiều vector đã xác nhận từ model card: **384**, `max_seq_length` **512 token**.

### Hai cạm bẫy môi trường đã kiểm chứng

**(a) `CREATE DATABASE` là tính năng Enterprise.** Neo4j Community Edition chỉ
cho phép đúng một database chuẩn, nên `CREATE DATABASE kb-hops` sẽ báo
`Unsupported administration command`. Neo4j Desktop có kèm Developer License của
Enterprise (cá nhân, một máy) nên cài qua Desktop thì chạy được. Nếu không,
`setup_neo4j.cypher` có sẵn Phương án B: dùng database mặc định `neo4j` và sửa
`NEO4J_DATABASE=neo4j` trong `.env`. `check_connection.py` tự nhận diện cả hai
lỗi này và in hướng xử lý cụ thể.

**(b) `pip install torch` mặc định là bản GPU.** Đã thử thật: lệnh này kéo về
`nvidia-cudnn-cu13` (366 MB), `nvidia-cusparselt` (170 MB), `nvidia-nccl`
(206 MB)… tổng khoảng 3 GB thư viện CUDA mà máy không GPU không dùng đến — đúng
điều đề bài dặn phải tránh. Phải cài bằng:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Xác nhận đúng bản: `torch.__version__` phải có hậu tố `+cpu`.

### Cảnh báo cắt ngắn khi nhúng

Model giới hạn 512 token. Trên dữ liệu thật có **11 chunk** (đều là bảng biểu,
dài 1.750–2.359 ký tự) có nguy cơ bị cắt — vector sẽ không phản ánh hết nội dung
bảng. `pipeline.py` in cảnh báo cho từng chunk này khi chạy `embed`/`load`,
**không tự cắt hay tự chia nhỏ**, vì quyết định xử lý bảng dài thuộc về người
thiết kế pipeline chứ không nên xảy ra ngầm.
