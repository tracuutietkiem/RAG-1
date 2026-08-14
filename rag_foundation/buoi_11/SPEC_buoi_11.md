# SPEC — Buổi 11: Multi-hop Graph RAG + Hỏi đáp bằng Gemini API

Tài liệu quy chiếu bắt buộc cho toàn bộ Buổi 11. Mọi prompt/code tiếp theo phải đọc
file này trước khi sửa. Đề bài gốc: `../../../buoi_11.md` (không sửa file đó).

> **Trạng thái:** Code đã viết xong, unit test offline chạy được (không cần
> Neo4j/Gemini thật). Việc tạo vector index trong Neo4j, gọi Gemini API thật và
> sinh `qa_comparison.md` với dữ liệu thật CHƯA chạy — cần `GEMINI_API_KEY` và
> Neo4j `kb-hops` đã nạp dữ liệu từ Buổi 10. Xem mục 8.

---

## 1. Mục tiêu và quan hệ với Buổi 10

Buổi 10 đã nạp 998 Chunk + 4 Document vào Neo4j `kb-hops`, có sẵn `embedding`
384 chiều trên mỗi Chunk và quan hệ liên văn bản (`CAN_CU`, hiện chưa có dữ
liệu `THAY_THE`/`HOP_NHAT` thật — xem mục 6). Buổi 11 **không nạp thêm dữ liệu
mới**, chỉ đọc và truy vấn đồ thị đã có, cộng thêm một **vector index** (thao
tác DB-level, không phải sửa file Buổi 10) để tìm kiếm ngữ nghĩa nhanh.

Buổi 11 **không sửa bất kỳ file nào trong `buoi_10/`**. Chỉ đọc `embedding.py`
làm tham chiếu cấu hình model (cùng model, cùng 384 chiều, để vector câu hỏi
và vector chunk nằm chung không gian nhúng).

Đề bài gốc gọi database là `lab1` ở phần Mục tiêu nhưng lại ghi rõ
**Database Name: `kb-hops`** ở Bước 1 — dùng `kb-hops` vì đó là database thật
đã tồn tại từ Buổi 10 và khớp với phần chi tiết kỹ thuật của đề bài.

---

## 2. Sơ đồ pipeline

```
Câu hỏi người dùng (text)
        │
        ▼
Bước 1 — Kết nối Neo4j kb-hops (src/graph_search.py, tái dùng Neo4jConfig)
        │
        ▼
Bước 2 — Tìm kiếm + mở rộng đa bước (src/graph_search.py)
        │   a. Nhúng câu hỏi bằng cùng model Buổi 10 (384 chiều)
        │   b. Vector search trong Neo4j (native vector index) → top-k chunk
        │      trực tiếp (hop=0), lấy luôn doc_id của các chunk này
        │   c. Nếu N (số bước nhảy) > 0: từ các doc_id ở hop=0, duyệt
        │      [:CAN_CU|THAY_THE|HOP_NHAT] cả hai chiều, tối đa N cạnh, tìm
        │      các Document lân cận ở khoảng cách 1..N
        │   d. Với mỗi Document lân cận, tính lại cosine similarity giữa
        │      vector câu hỏi và các Chunk của riêng Document đó, lấy
        │      top-k-per-hop chunk tốt nhất (không lấy toàn bộ chunk của văn
        │      bản lân cận — tránh tràn ngữ cảnh)
        │   e. Gộp danh sách chunk hop=0..N, loại trùng theo chunk_id, giữ
        │      khoảng cách hop nhỏ nhất nếu trùng
        ▼
Bước 3 — Build prompt + gọi Gemini (src/gemini_qa.py)
        │   System prompt mô tả schema đồ thị + cấu trúc Chương/Điều/Khoản và
        │   quy tắc "chỉ trả lời từ ngữ cảnh, nói rõ nếu thiếu thông tin"
        │   Model: gemini-flash-latest
        ▼
Bước 4 — CLI (src/pipeline.py)
        ask       — hỏi 1 câu, chọn --hops N tuỳ ý, in ra câu trả lời + nguồn
        compare   — chạy 5 câu hỏi mẫu ở hops=0,1,2, ghi qa_comparison.md
```

---

## 3. Cấu trúc project

```
rag_foundation/buoi_11/
├── SPEC_buoi_11.md          ← file này
├── README.md                 hướng dẫn chạy, cài đặt, biến môi trường
├── requirements.txt
├── .env.example               không commit .env thật (chứa API key, mật khẩu)
├── setup_vector_index.cypher  lệnh tạo vector index trên (:Chunk).embedding
├── chay_buoi_11.ps1           script tự động chạy toàn bộ (giống Buổi 10)
├── src/
│   ├── __init__.py
│   ├── graph_search.py        Bước 1–2 — kết nối + tìm kiếm multi-hop
│   ├── gemini_qa.py            Bước 3 — prompt + gọi Gemini API
│   └── pipeline.py             CLI: ask, compare
├── tests/                      unit test, offline hoàn toàn
│   ├── test_graph_search.py    dùng FakeSession, không cần Neo4j thật
│   ├── test_gemini_qa.py       dùng fake call_fn, không cần API key thật
│   └── test_pipeline.py
├── data/
│   └── test_questions.md       5 câu hỏi kiểm thử từ đề bài (mục 4)
└── reports/
    └── qa_comparison.md        kết quả so sánh 0/1/2 bước nhảy (sinh khi chạy `compare`)
```

---

## 4. Vector search trong Neo4j

Dùng **native vector index** của Neo4j (GA từ 5.13, instance Buổi 10 dùng
2026.07 nên chắc chắn hỗ trợ) thay vì brute-force cosine trong Python — đúng
tinh thần đề bài "Thực hiện tìm kiếm vector trong Neo4j".

`setup_vector_index.cypher`:

```cypher
:use kb-hops
CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}};
```

Truy vấn (trong `graph_search.py`):

```cypher
CALL db.index.vector.queryNodes('chunk_embedding_index', $k, $query_vector)
YIELD node, score
MATCH (top:Chunk)-[:PARENT_OF*0..]->(node)
WHERE NOT ()-[:PARENT_OF]->(top)
MATCH (top)-[:PART_OF]->(d:Document)
RETURN node.chunk_id AS chunk_id, node.text AS text, node.heading AS heading,
       d.doc_id AS doc_id, node.level AS level, score
```

> **Lỗi đã gặp thật (đã sửa):** bản đầu tiên dùng thẳng `node.doc_id`, nhưng
> Chunk không lưu `doc_id` làm thuộc tính (chỉ Chunk gốc mới nối `PART_OF` tới
> Document — xem `SPEC_buoi_10.md` mục 5) nên mọi kết quả ra `doc_id=None`, kéo
> theo multi-hop hoàn toàn không hoạt động (không tìm được Document gốc nên
> không mở rộng được). Phải truy ngược lên Chunk gốc rồi mới lấy `doc_id` từ
> Document như trên. Xem REVIEW_buoi_11.md.

`graph_search.py` tự kiểm tra index đã tồn tại chưa (`SHOW INDEXES`) trước khi
chạy `ask`/`compare`; nếu chưa có, in hướng dẫn chạy `setup_vector_index.cypher`
thay vì tự âm thầm tạo (nhất quán với cách Buổi 10 xử lý `CREATE DATABASE` —
thao tác cấu trúc DB phải tường minh, không chạy ngầm).

---

## 5. Mở rộng đa bước (Multi-hop)

- **Hướng duyệt**: không phân biệt chiều `CAN_CU`/`THAY_THE`/`HOP_NHAT` khi
  mở rộng (`-[:CAN_CU|THAY_THE|HOP_NHAT]-` không mũi tên) — vì cả "văn bản A
  căn cứ B" lẫn "văn bản B được A căn cứ" đều là ngữ cảnh liên quan khi tra
  cứu, đề bài không yêu cầu chỉ một chiều.
- **Số bước nhảy N** (`--hops`, mặc định 0): N=0 nghĩa là không mở rộng, chỉ
  dùng kết quả vector search trực tiếp — dùng làm baseline so sánh.
- **Trần số lượng**: `top_k_direct` (mặc định 5) chunk ở hop 0,
  `top_k_per_hop` (mặc định 2) chunk cho mỗi Document lân cận ở mỗi mức hop —
  tránh một câu hỏi kéo theo toàn bộ 998 chunk vào prompt.
- **Loại trùng**: một chunk chỉ xuất hiện một lần trong ngữ cảnh cuối, ưu tiên
  giữ khoảng cách hop nhỏ nhất nếu trùng.
- **Nguồn trích dẫn**: mỗi đoạn ngữ cảnh đưa vào prompt kèm `doc_id` +
  `heading` để LLM (và người đọc log) biết đoạn nào tới từ văn bản nào, ở hop
  bao nhiêu.

---

## 6. Giới hạn dữ liệu thật (phải nói rõ, không che giấu)

Theo REVIEW_buoi_10.md, dữ liệu Neo4j hiện có **chỉ có 4 Document** (Thông tư
41/2016/TT-NHNN + 3 văn bản viện dẫn dạng stub) và **3 quan hệ `CAN_CU`**,
không có `THAY_THE`/`HOP_NHAT` nào. Điều này có nghĩa:

- 5 câu hỏi kiểm thử ở đề bài Buổi 11 (mục 4) tham chiếu tới các văn bản
  **không có trong đồ thị hiện tại** (Nghị định 46/2023/NĐ-CP, Văn bản hợp
  nhất 52/VBHN-NHNN, Thông tư 01/2025/TT-NHNN...) — chỉ có Câu hỏi 4 (Thông
  tư 41/2016/TT-NHNN căn cứ luật nào) là khớp được với dữ liệu thật.
- Với 4 câu hỏi còn lại, hệ thống **phải trả lời "không có thông tin trong
  ngữ cảnh"** thay vì bịa — đây chính là phép thử đúng cho yêu cầu "nêu rõ
  nếu ngữ cảnh không có thông tin thay vì tự suy đoán" ở đề bài Bước 3.
  `qa_comparison.md` sẽ ghi nhận trung thực kết quả này, không tự chế thêm dữ
  liệu để 5 câu đều "trả lời được" cho đẹp.
- Muốn kiểm thử đủ ý nghĩa cho cả 5 câu, cần nạp thêm các văn bản liên quan
  vào Buổi 10 trước (bổ sung `data/raw_html/` và
  `data/doc_relationships.json` ở Buổi 10, không sửa gì ở Buổi 11).

---

## 7. Biến môi trường (`.env`, xem `.env.example`)

```ini
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=                     # KHÔNG commit giá trị thật — dùng lại mật khẩu Buổi 10
NEO4J_DATABASE=kb-hops

EMBEDDING_MODEL=thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5
EMBEDDING_DEVICE=cpu                # bắt buộc cpu, giống Buổi 10

GEMINI_API_KEY=                     # KHÔNG commit giá trị thật
GEMINI_MODEL=gemini-flash-latest

TOP_K_DIRECT=5
TOP_K_PER_HOP=2
```

Không commit `.env` thật. Không đưa số liệu khách hàng, dữ liệu nội bộ chưa
công bố vào `data/`, `reports/`.

---

## 8. Testability và dependency injection

Cùng phong cách Buổi 10 — mọi thành phần chạm mạng/model phải tiêm được fake:

- `graph_search.py`: `driver_factory` và `embed_fn` injectable; test dùng
  `FakeSession` ghi lại Cypher đã chạy và trả kết quả giả định sẵn, không mở
  kết nối Neo4j thật, không tải model thật.
- `gemini_qa.py`: `call_fn` injectable (nhận prompt, trả text) — test không
  gọi API thật, không cần `GEMINI_API_KEY`.
- `pipeline.py`: `cmd_ask`/`cmd_compare` nhận toàn bộ dependency qua tham số,
  test bằng cách tiêm fake cho cả ba (Neo4j, embedding, Gemini) và kiểm tra
  `qa_comparison.md` sinh ra đúng cấu trúc (không assert nội dung câu trả
  lời thật vì đó phụ thuộc Gemini).

---

## 9. Việc còn lại phải làm trên máy người dùng

1. Đảm bảo Neo4j `kb-hops` đang chạy và đã nạp dữ liệu Buổi 10 (đã xong).
2. Chạy `setup_vector_index.cypher` (qua Neo4j Browser hoặc
   `python check_index.py`) để tạo vector index — chỉ cần chạy một lần.
3. Lấy `GEMINI_API_KEY` tại Google AI Studio, điền vào `.env`.
4. Copy `.env.example` → `.env`, điền `NEO4J_PASSWORD` (giống Buổi 10) và
   `GEMINI_API_KEY`.
5. Chạy `python -m src.pipeline compare` để sinh `reports/qa_comparison.md`
   thật với 5 câu hỏi ở hops=0,1,2.

## 10. Phạm vi ghi

Chỉ ghi trong `rag_foundation/buoi_11/`. Không sửa code/dữ liệu/storage của
Buổi 05–10. Vector index là thao tác DB-level trên database `kb-hops` dùng
chung, không phải file — được phép vì đề bài Buổi 11 yêu cầu trực tiếp.
