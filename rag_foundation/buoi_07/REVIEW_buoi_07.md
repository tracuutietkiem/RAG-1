# Nghiệm thu Buổi 07

Đối chiếu từng mục bắt buộc trong [`SPEC_buoi_07.md`](./SPEC_buoi_07.md) với
kết quả thực tế đã build và đã xác nhận trên máy thật (Windows, `.venv` của
Buổi 05).

## Workspace

- Chỉ ghi trong `rag_foundation/buoi_07/`. Không sửa code/output Buổi 05,
  không sửa code/storage Buổi 06 kể từ Prompt 02. **Đạt.**
- Ngoại lệ duy nhất (tạo `buoi_05/.venv/` + `buoi_05/requirements.txt` ở
  Prompt 01, vì trước đó Buổi 05 chưa có venv riêng) đã ghi rõ lý do trong
  SPEC. **Đạt, có ghi chú minh bạch.**

## Python & Packages

- Dùng `.venv` của Buổi 05 (`buoi_05/.venv/Scripts/python.exe`), không tạo
  venv mới ở Buổi 07. **Đạt** — xác nhận qua các lệnh CLI/test chạy thành
  công trên máy thật bằng đúng interpreter này.
- Chỉ dùng `streamlit`, `google-genai`, `chromadb`, `python-dotenv` +
  thư viện chuẩn (`argparse`, `hashlib`, `json`, `math`, `os`, `re`,
  `tempfile`, `unittest`, `unittest.mock`). Không dùng LangChain/LlamaIndex/
  PostgreSQL/pytest/reranker. **Đạt** — xem `import` ở đầu `rag.py`.

## Input & Data Contract

- Chunk JSON của Buổi 05 là black box, không OCR/parse/chunk lại. **Đạt.**
- Alias `fixed_size` (Buổi 05) -> `fixed-size` (chuẩn Buổi 07) xử lý qua
  `STRATEGY_ALIASES`, xác nhận trên dữ liệu thật: 259 chunk fixed-size vẫn
  load được qua alias. **Đạt.**
- `validate_chunk`/`load_chunks` chặn đủ: thiếu field, sai kiểu, page
  boolean/không nguyên/< 1/`page_start > page_end`, strategy không hợp lệ,
  `chunk_id` trùng lặp; bỏ qua (không fail) `text` rỗng sau strip và đếm vào
  `empty_text_skipped`. **Đạt** — 24 test case trong `LoadChunksTests` +
  `ValidateChunkTests`, đã chạy thật với 821 record / 3 file thật của Buổi 05
  (kết quả: 259 fixed-size, 163 semantic, 399 hierarchical hợp lệ).

## Index Contract

- Một strategy = một collection ChromaDB riêng, tên gồm strategy + dimension
  + hash ổn định của tên model (`collection_name`, không hard-code hash mẫu).
  **Đạt.**
- Dùng embedding Gemini thật, không vector giả (zero/random/hash/fallback
  cục bộ). `index` không có `GEMINI_API_KEY` báo lỗi rõ ràng và dừng, không
  tạo dữ liệu giả — xác nhận trên máy thật (lệnh `index` khi chưa dán key).
  **Đạt.**
- Validate toàn bộ embedding (đếm, dimension, NaN, Infinity, boolean,
  zero-vector) **trước khi** đụng ChromaDB; `--reset` chỉ xoá đúng collection
  đích và chỉ xoá **sau khi** embedding đã validate thành công — xác nhận qua
  test giả lập lỗi embedding giữa chừng (collection cũ còn nguyên dù có
  `--reset`). **Đạt.**
- `status` chỉ đọc, không tạo collection. **Đạt** — xác nhận cả code lẫn máy
  thật (chạy `status` trước khi index chưa từng thấy collection nào bị tạo).
- Idempotent: index 2 lần liên tiếp không tăng `record_count` (dùng
  `upsert` theo `chunk_id`). **Đạt** — xác nhận qua test + trên máy thật
  (399/399 record ổn định sau nhiều lần chạy).
- **Xác nhận trên máy thật với dữ liệu production:** `index --strategy
  hierarchical` chạy thành công 399/399 chunk, `status` báo đúng
  `record_count: 399`, `metadata_ok: Có`.

## Retrieval Contract

- Evidence thật kèm `distance` lấy trực tiếp từ Chroma, không tự chế điểm số.
  **Đạt.**
- Confidence gate theo `RAG_MAX_DISTANCE`: evidence không đạt ngưỡng không
  được đưa vào prompt sinh câu trả lời; không evidence nào đạt ngưỡng thì
  trạng thái `insufficient_evidence` và **không gọi** Gemini generation.
  **Đạt** — xác nhận qua test (`test_ask_insufficient_evidence_skips_generation`,
  đếm `gen_calls` = 0 trong trường hợp này) và triển khai (`ask()` return sớm
  trước khi gọi `generate_answer`).

## Citation Contract

- Citation map từ metadata thật trong Chroma bằng code, không tin
  source/page/chunk_id do LLM tự viết. **Đạt.**
- `ask()`/`query` luôn có đủ field: `status`, `answer`, `evidence`,
  `citations`, `warnings`, `collection`, `strategy`, `top_k`. **Đạt** — test
  `test_ask_returns_required_fields`.
- Nhãn không hợp lệ (`[E99]`) bị loại khỏi answer, ghi cảnh báo, không biến
  thành citation giả. **Đạt** — xác nhận cả offline (test) lẫn có thể tái
  hiện thật trên máy (LLM thật của người dùng không sinh nhãn giả trong lần
  chạy thật, nhưng đường xử lý đã được test riêng để đảm bảo an toàn nếu xảy
  ra).
- **Xác nhận trên máy thật:** câu hỏi "Điều kiện cấp tín dụng..." và "rủi ro
  là gì" đều trả `status: answered`, citation trỏ đúng trang/chunk_id thật
  trong văn bản NHNN, model tự nhận không đủ căn cứ cho phần không có trong
  tài liệu thay vì suy đoán — đúng tinh thần "grounded, không bịa".

## Security

- Không in giá trị API key trong bất kỳ thông báo lỗi nào — xác nhận qua
  `SecurityTests` (chèn secret giả vào `Config`, ép lỗi, assert secret không
  xuất hiện trong exception message) cho cả `ConfigError` và `EmbeddingError`
  (kể cả lỗi khởi tạo client, không chỉ lỗi gọi API — đã bổ sung try/except
  bọc `client_factory()` sau khi phát hiện qua test).
- `.env` trong `.gitignore`, không commit. **Đạt** (đã kiểm tra
  `.gitignore` từ Prompt 01/02).
- Đã xác nhận văn bản nguồn là công khai trước khi đưa vào pipeline gọi API
  bên ngoài (đã hỏi và được người dùng xác nhận ở Buổi 06/07 trước khi xử
  lý).

## Testing

- `unittest`, không `pytest`. **Đạt.**
- 69 test case, `tests/test_rag.py`, chạy offline hoàn toàn (Gemini mock qua
  `client_factory`, Chroma dùng `tempfile`, không đụng `storage/chroma/`
  thật, không gọi Internet). **Đạt** — xác nhận trên máy thật:
  `Ran 69 tests in 8.875s / OK`.

## Coding Style

- Một file `rag.py` duy nhất chứa toàn bộ logic (không kiến trúc nhiều
  tầng), UI (`app.py`) chỉ gọi hàm public, test chỉ dùng tham số hàm đơn giản
  để mock (`client_factory`, `persist_path`, `input_dir`, `env_path`) —
  không dùng framework DI. **Đạt.**

## Kết luận

Toàn bộ 9 prompt đã hoàn thành và được xác nhận bằng chạy thật trên máy
Windows của người dùng (không chỉ test trong sandbox), bao gồm: loader/
validator trên 821 record thật, index 399 chunk thật qua Gemini + ChromaDB
thật, truy vấn thật với câu trả lời có trích dẫn đúng, giao diện Streamlit
chạy được, và 69 test tự động PASS. Không còn mục nào trong SPEC_buoi_07.md
chưa được đáp ứng.
