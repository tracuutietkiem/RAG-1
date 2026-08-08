# SPEC — Buổi 07: Hoàn thiện RAG Pipeline với AI Agent

Tài liệu quy chiếu bắt buộc cho toàn bộ Buổi 07. Mọi prompt tiếp theo phải đọc
file này trước khi sửa code.

## Workspace

Vùng được đọc:
- `rag_foundation/buoi_05/output/chunks/`
- `rag_foundation/buoi_05/.venv/`
- `rag_foundation/buoi_06/`
- `rag_foundation/buoi_07/`

Vùng được ghi: chỉ `rag_foundation/buoi_07/`.

Không sửa code/output Buổi 05, không sửa code/storage Buổi 06. Ngoại lệ duy
nhất đã xảy ra ở Prompt 01: tạo `rag_foundation/buoi_05/.venv/` (chưa từng có)
và `rag_foundation/buoi_05/requirements.txt` (chưa từng có) — vì Buổi 07 bắt
buộc dùng venv riêng của Buổi 05 và không có sẵn cách nào khác để tạo venv đó
mà không thêm requirements.txt tương ứng. Từ Prompt 02 trở đi, không đụng tới
Buổi 05/06 nữa.

## Python

Dùng `.venv` của Buổi 05, không tạo virtual environment mới:
- Windows: `rag_foundation/buoi_05/.venv/Scripts/python.exe`
- Linux/macOS: `rag_foundation/buoi_05/.venv/bin/python`

## Input

- JSON trong `rag_foundation/buoi_05/output/chunks/` là nguồn dữ liệu duy
  nhất, Buổi 05 coi là black box đã chuẩn bị sẵn.
- Không OCR, không parse PDF, không chunk lại.
- **Lưu ý quan trọng:** dữ liệu thật của Buổi 05 dùng giá trị
  `strategy: "fixed_size"` (gạch dưới), trong khi Data Contract của Buổi 07
  chuẩn hoá tên `"fixed-size"` (gạch ngang, xem mục Data Contract). Loader ở
  Bước 04 phải xử lý rõ ràng sai khác này (chấp nhận cả hai dạng khi đọc dữ
  liệu thật, chuẩn hoá về `fixed-size` khi lưu/hiển thị), không được âm thầm
  bỏ qua toàn bộ chunk `fixed_size` của Buổi 05.

## Packages

Chỉ dùng trực tiếp: `streamlit`, `google-genai`, `chromadb`, `python-dotenv`.
Thư viện chuẩn được phép: `argparse`, `hashlib`, `json`, `math`, `os`,
`pathlib`, `re`, `tempfile`, `unittest`, `unittest.mock`.

Không dùng: LangChain, LlamaIndex, framework RAG khác, PostgreSQL, database
tự quản lý, OCR/PDF parser, reranker, hybrid search, agent framework,
pytest, kiến trúc nhiều tầng phức tạp.

## Pipeline

validate → embedding → Chroma persistent → retrieval → confidence gate →
generation → citation → Streamlit → unittest offline.

## Data Contract

Trường bắt buộc mỗi chunk: `chunk_id`, `strategy`, `source`, `page_start`,
`page_end`, `text`.

- `chunk_id`, `strategy`, `source`, `text`: string, không rỗng sau `strip()`
  (riêng `text` được phép rỗng nhưng bị đếm vào `empty_text_skipped` và bỏ
  qua thay vì fail).
- `strategy` chỉ nhận: `fixed-size`, `semantic`, `hierarchical` (sau chuẩn
  hoá — xem lưu ý ở mục Input về `fixed_size` của Buổi 05).
- `page_start`, `page_end`: integer (không chấp nhận boolean), ≥ 1,
  `page_start <= page_end`.
- `chunk_id` duy nhất trong tập chunk được chọn (theo từng strategy).

## Index Contract

- Một strategy nằm trong một collection ChromaDB riêng.
- Model và dimension của embedding lúc index và lúc query phải khớp nhau.
- Dùng embedding thật từ Gemini — không dùng vector giả (zero, random, hash,
  hay embedding fallback cục bộ nào khác).
- Chặn: NaN, Infinity, boolean, zero vector, sai dimension, sai số lượng vector.
- ChromaDB dùng cosine distance qua
  `configuration={"hnsw": {"space": "cosine"}}`, luôn truyền tường minh
  `embedding_function=None`.
- Index idempotent: chạy `index` nhiều lần không tăng số record (dùng `upsert`
  theo `chunk_id`).
- `status` là thao tác read-only, không được tạo collection mới.
- Phải tạo và validate toàn bộ embedding thành công trước khi reset hoặc
  upsert — không index/reset nửa chừng.

## Retrieval Contract

- Trả evidence thật kèm `distance` lấy từ Chroma.
- Chỉ evidence đạt ngưỡng `RAG_MAX_DISTANCE` (accepted = true) mới được đưa
  vào prompt sinh câu trả lời.
- Nếu không có evidence nào đạt ngưỡng: trạng thái `insufficient_evidence`,
  không gọi Gemini generation.

## Citation Contract

- Citation được map từ metadata thật trong Chroma bằng code, không tin
  source/page/chunk_id do LLM tự tạo ra trong văn bản trả lời.
- Kết quả `ask()`/`query` luôn có đủ field: `status`, `answer`, `evidence`,
  `citations`, `warnings`, `collection`, `strategy`, `top_k`.
- Label không hợp lệ (vd `[E99]`) bị loại khỏi answer và ghi cảnh báo vào
  `warnings`, không được biến thành citation giả.

## Security

- Không in giá trị API key, không hard-code secret, không in toàn bộ `.env`.
- `.env` nằm trong `.gitignore`, không commit.
- Exception/log không chứa secret.

## Testing

- Dùng `unittest` (không dùng `pytest`).
- Mock Gemini embedding/generation — test không gọi Internet, không cần API
  key thật.
- Dùng thư mục tạm (`tempfile`) cho Chroma test, không đụng
  `storage/chroma/` thật.

## Coding Style

Ưu tiên ít file, ít class, ít function, dễ đọc. Không thêm kiến trúc nhiều
tầng, không dependency injection framework — chỉ dùng tham số hàm đơn giản
để có thể mock/test.
