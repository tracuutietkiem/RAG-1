# Buổi 07 — RAG hoàn thiện với AI Agent

Hoàn thiện pipeline RAG bắt đầu từ chunk JSON đã có sẵn của Buổi 05: embedding
Gemini thật, index ChromaDB persistent, truy vấn semantic có confidence gate,
sinh câu trả lời có trích dẫn (citation) map từ metadata thật, giao diện
Streamlit, và bộ test tự động chạy offline.

Đặc tả kỹ thuật đầy đủ (ràng buộc bắt buộc): [`SPEC_buoi_07.md`](./SPEC_buoi_07.md).
Ghi chú tiến độ theo từng prompt: [`buoi_07.md`](./buoi_07.md).

## Pipeline

```
Chunk JSON của Buổi 05 (chỉ đọc)
  -> validate (chunk_id/strategy/source/page/text)
  -> Gemini embedding (model/dimension cấu hình qua .env)
  -> ChromaDB persistent index (1 collection / strategy, cosine distance)
  -> truy vấn semantic top-k
  -> confidence gate (RAG_MAX_DISTANCE)
  -> Gemini sinh câu trả lời (chỉ dùng evidence đạt ngưỡng)
  -> map citation [E#] -> metadata thật (source/trang/chunk_id) bằng code
```

## Chuẩn bị môi trường

Dùng `.venv` sẵn có của Buổi 05 (không tạo venv mới):

```
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG
..\buoi_05\.venv\Scripts\python.exe -m pip install -r rag_foundation\buoi_07\requirements.txt
```

Sửa `rag_foundation\buoi_07\.env`, dán key thật vào dòng `GEMINI_API_KEY=`.
Không commit file `.env` (đã có trong `.gitignore`), không chia sẻ key qua
chat hay nơi không an toàn.

Biến cấu hình trong `.env`:

| Biến | Ý nghĩa |
| --- | --- |
| `GEMINI_API_KEY` | API key Gemini — để trống thì `validate`/`status` vẫn chạy được, `index`/`query` sẽ báo lỗi rõ ràng |
| `GEMINI_EMBEDDING_MODEL` | Tên model embedding |
| `GEMINI_EMBEDDING_DIM` | Số chiều vector (128–3072) |
| `GEMINI_GENERATION_MODEL` | Tên model sinh câu trả lời |
| `DEFAULT_TOP_K` | Số evidence lấy ra mặc định khi không truyền `--top-k` (1–20) |
| `RAG_MAX_DISTANCE` | Ngưỡng cosine distance để evidence được coi là "đạt" (≥ 0) |

## Lệnh CLI

Tất cả chạy từ thư mục `RAG`, dùng Python của venv Buổi 05:

```
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG

REM Kiểm tra dữ liệu chunk của Buổi 05 (không cần key)
.\rag_foundation\buoi_05\.venv\Scripts\python.exe .\rag_foundation\buoi_07\rag.py validate --strategy hierarchical

REM Xem trạng thái hệ thống (chỉ đọc, không tạo collection, không cần key)
.\rag_foundation\buoi_05\.venv\Scripts\python.exe .\rag_foundation\buoi_07\rag.py status --strategy hierarchical

REM Embed + index vào ChromaDB (cần GEMINI_API_KEY, có thể mất vài phút)
.\rag_foundation\buoi_05\.venv\Scripts\python.exe .\rag_foundation\buoi_07\rag.py index --strategy hierarchical
.\rag_foundation\buoi_05\.venv\Scripts\python.exe .\rag_foundation\buoi_07\rag.py index --strategy hierarchical --reset

REM Hỏi đáp (cần đã index trước, cần GEMINI_API_KEY)
.\rag_foundation\buoi_05\.venv\Scripts\python.exe .\rag_foundation\buoi_07\rag.py query --strategy hierarchical --question "Câu hỏi của bạn" --top-k 5
```

`--strategy` nhận `fixed-size`, `semantic`, hoặc `hierarchical` — mỗi strategy
là một collection ChromaDB riêng, phải `index` riêng trước khi `query`.

## Giao diện Streamlit

```
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_07
..\buoi_05\.venv\Scripts\streamlit.exe run app.py
```

Giao diện chỉ gọi lại các hàm public trong `rag.py` — mọi logic RAG đều nằm
trong `rag.py`, có thể tái sử dụng qua CLI hoặc UI như nhau.

## Chạy bộ test tự động

```
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_07
..\buoi_05\.venv\Scripts\python.exe -m unittest tests.test_rag -v
```

69 test case (`unittest`), chạy hoàn toàn offline: không gọi Internet, không
cần `GEMINI_API_KEY` thật (Gemini được mock qua `client_factory`), không đụng
`storage/chroma/` thật (mỗi test dùng thư mục tạm riêng, tự xoá sau khi chạy).

## Kết quả trạng thái (`status`)

`ask()`/`query` luôn trả một trong ba trạng thái:

- `answered` — có evidence đạt ngưỡng và Gemini sinh được câu trả lời có trích dẫn.
- `insufficient_evidence` — không evidence nào đạt `RAG_MAX_DISTANCE`; **không**
  gọi Gemini sinh câu trả lời (tránh trả lời không có căn cứ).
- `retrieval_only` — có evidence đạt ngưỡng nhưng bước sinh câu trả lời lỗi
  hoặc trả về rỗng; vẫn trả evidence/citation, không giả vờ có câu trả lời.

Citation (`[E1]`, `[E2]`, ...) luôn được map về metadata thật (source, trang,
chunk_id) bằng code — nhãn không hợp lệ do model tự sinh ra bị loại khỏi câu
trả lời và ghi vào `warnings`, không bao giờ trở thành citation giả.

## Bảo mật

- Không hard-code API key, không in giá trị key ra log/console trong bất kỳ
  thông báo lỗi nào.
- `.env` nằm trong `.gitignore`, không commit.
- Không dùng vector giả (zero/random/hash) khi thiếu key — `index`/`query`
  báo lỗi rõ ràng và dừng lại thay vì chạy với dữ liệu giả.
- Nội dung tài liệu nguồn (`2026-08-01_TaiLieu_NHNNSigned`) đã được xác nhận
  là văn bản công khai trước khi đưa vào pipeline gọi API bên ngoài (Gemini).
  Không đưa dữ liệu khách hàng, số liệu nội bộ chưa công bố, hoặc dữ liệu định
  danh cá nhân vào pipeline này.

## Giới hạn đã biết

- Embedding gọi Gemini tuần tự từng chunk (không batch) theo đúng yêu cầu
  SPEC — index toàn bộ 399 chunk hierarchical mất vài phút.
- Chỉ dùng cho mục đích tra cứu tham khảo; kết quả từ mô hình sinh ngôn ngữ
  vẫn cần đối chiếu với văn bản gốc và quy định hiện hành trước khi dùng cho
  quyết định nghiệp vụ thực tế (thẩm định, cấp tín dụng, ...).
