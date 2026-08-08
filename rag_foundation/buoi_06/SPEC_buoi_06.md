# SPEC — Buổi 6: RAG với AI Agent (Streamlit + Gemini + ChromaDB + PostgreSQL)

Tài liệu này là kim chỉ nam cho toàn bộ Buổi 6. Mọi bước code (`rag.py`,
`app.py`) phải tuân theo đúng các mục dưới đây.

## Workspace

Chỉ được phép đọc/ghi trong:
- `RAG/rag_foundation/buoi_05/output/chunks/` (chỉ **đọc**, là nguồn dữ liệu đầu vào)
- `RAG/rag_foundation/buoi_06/` (đọc/ghi, project chính)

Không đọc:
- Source code của Buổi 5 (`buoi_05/src/`, `SPEC_buoi_05.md`, `REVIEW_buoi_05.md`, ...)
- README/tài liệu các buổi trước
- Notebook, git history, thư mục khác

Buổi 5 là **black box** — chỉ dùng JSON trong `output/chunks/` làm dữ liệu
đầu vào, không phân tích/tái sử dụng logic bên trong Buổi 5.

**Điều chỉnh so với đề bài gốc:** đề bài yêu cầu dùng `buoi_05/.venv/`, nhưng
Buổi 5 trong project này không tạo virtual environment (cài thư viện thẳng
vào Python hệ thống). Theo quyết định của người dùng, Buổi 6 dùng lại đúng
Python hệ thống đó, không tạo venv mới.

## Python

Sử dụng Python hệ thống (interpreter đã dùng ở Buổi 5): `C:\Python314\python.exe`.
Không tạo virtual environment mới.

## Package

Chỉ cài:
- `streamlit`
- `google-genai`
- `chromadb`
- `psycopg[binary]`
- `python-dotenv`

Không cài framework khác (không FastAPI, không LangChain, không LlamaIndex).

## Coding Style

Ưu tiên: ít file, ít class, ít function, code dễ đọc, dễ dạy cho người mới.
Không tạo: repository pattern, service layer, dependency injection, factory,
plugin.

## Scope

Chỉ cần: index, retrieval, answer, giao diện Streamlit.
Không phát triển ngoài yêu cầu (không auth, không multi-user, không cache
layer riêng, không hàng đợi/queue).

## Kiến trúc lưu trữ

- **PostgreSQL** (`rag_db`): lưu **text gốc + metadata** của từng chunk
  (bảng `chunks`: `chunk_id`, `source`, `strategy`, `page_start`, `page_end`,
  `text`, `structure_path`).
- **Fallback khi không có PostgreSQL**: lưu vào file SQLite cục bộ
  `storage/local_fallback.db` — cùng schema bảng `chunks`, dùng thư viện
  `sqlite3` chuẩn của Python (không cần cài thêm package).
- **ChromaDB** (`storage/chroma/`, Embedded PersistentClient): chỉ lưu
  **vector embedding** + `chunk_id` để map ngược sang text (không lưu lại
  toàn bộ text trong Chroma để tránh trùng lặp — Chroma chỉ dùng cho
  retrieval, text thật lấy từ PostgreSQL/SQLite).
- Ưu tiên kết nối Chroma Server nếu đang chạy sẵn (`chromadb.HttpClient`);
  nếu không có, dùng Embedded Persistent Client (`chromadb.PersistentClient`).

## Embedding

Dùng `google-genai`, model `gemini-embedding-2`, `output_dimensionality=384`
(để đồng bộ kích thước với embedding fallback mặc định của ChromaDB —
all-MiniLM-L6-v2, 384 chiều).

**Chế độ suy giảm khi thiếu `GEMINI_API_KEY`:**
- `index()`: **bắt buộc** cần key hợp lệ để tạo embedding — nếu thiếu key,
  dừng lại và báo lỗi rõ ràng, không index được.
- `ask(question)`: nếu **đã có** dữ liệu index từ trước nhưng **hiện tại**
  thiếu key, vẫn cho phép retrieval bằng cách embed câu hỏi qua embedding
  mặc định của ChromaDB (all-MiniLM-L6-v2, cùng 384 chiều) thay vì Gemini,
  và **bỏ qua bước gọi Gemini sinh câu trả lời** (chỉ trả về danh sách top-k
  kèm cảnh báo "đang ở chế độ chỉ tra cứu, không có API key"). Lưu ý: đây là
  giải pháp demo — vector từ 2 nguồn embedding khác nhau không cùng không
  gian ngữ nghĩa nên độ chính xác retrieval trong chế độ này chỉ mang tính
  minh hoạ, không phản ánh chất lượng thật của hệ thống khi có đủ key.

## Sinh câu trả lời (generation)

Dùng `google-genai`, model `gemini-flash-lite-latest`. Prompt đơn giản: ghép
câu hỏi + các đoạn top-k tìm được, yêu cầu trả lời dựa trên ngữ cảnh cung cấp.

## Error Handling

Chỉ cần try/except tối thiểu ở các điểm gọi dịch vụ ngoài (PostgreSQL,
ChromaDB, Gemini). Không cần retry, không cần logging framework, không cần
monitoring. Lỗi hiển thị thông báo tiếng Việt ngắn gọn cho người dùng.

## Security

Không in ra console/UI: API key, mật khẩu PostgreSQL, secret khác. Không
hard-code thông tin nhạy cảm trong code — chỉ đọc từ `.env`.

## Code Size

Mục tiêu khoảng 300–500 dòng Python cho toàn bộ project (`app.py` + `rag.py`).
Nếu vượt khoảng 700 dòng, phải đơn giản hoá thiết kế thay vì thêm tính năng.

## Checklist hoàn thành

- [ ] Dùng đúng Python hệ thống đã thống nhất, không tạo venv mới.
- [ ] Chỉ đọc JSON trong `buoi_05/output/chunks/`, không đụng code Buổi 5.
- [ ] PostgreSQL lưu text + metadata; có fallback SQLite cục bộ khi thiếu Postgres.
- [ ] ChromaDB lưu vector embedding (Embedded Persistent Client mặc định).
- [ ] Gemini dùng `google-genai`, model `gemini-embedding-2` (embedding) và
      `gemini-flash-lite-latest` (trả lời).
- [ ] Streamlit hiển thị được danh sách top-k và câu trả lời.
- [ ] Không lộ API key/mật khẩu trong code, log, hay giao diện.
- [ ] Tổng số dòng mã nguồn khoảng 300–500 dòng Python.
