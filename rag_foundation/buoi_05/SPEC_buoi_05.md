# SPEC — Buổi 5: RAG Foundation (OCR + Chunking) — bản demo

## 1. Phạm vi

Xây dựng một thành phần RAG Foundation **độc lập**, chỉ nằm trong
`RAG/rag_foundation/buoi_05/`. Mục tiêu là minh hoạ luồng: PDF → text (đọc
trực tiếp hoặc OCR) → chuẩn hoá → chunk, theo ba chiến lược chunking khác
nhau, để người học quan sát được từng bước.

**Không thuộc phạm vi Buổi 5** (không được làm): tạo embedding, lưu vector
database, gọi LLM để sinh nội dung/tóm tắt.

## 2. Đầu vào

- File PDF tiếng Việt đặt trong `datademo/`. PDF phải là tài liệu công khai
  hoặc mô phỏng — không dùng dữ liệu khách hàng, số liệu nội bộ chưa công bố,
  hay thông tin định danh cá nhân.
- Biến môi trường `LLAMA_CLOUD_API_KEY` đọc từ `src/.env` bằng
  `python-dotenv` / `os.getenv`. Code được phép **sử dụng** giá trị của key
  để gọi API, nhưng **không được đọc ra để in, log, hay lưu vào file kết
  quả** dưới bất kỳ hình thức nào (kể cả một phần key).

## 3. Luồng xử lý (pipeline)

1. **Đọc PDF** bằng PyMuPDF (`pymupdf`), duyệt từng trang.
2. **Thử lấy text layer** trực tiếp từ PyMuPDF cho từng trang.
3. **Fallback OCR toàn file** bằng LlamaParse (`llama_cloud`) khi phát hiện
   một trong các điều kiện lỗi sau ở bất kỳ trang nào:
   - Lỗi font / không trích được ký tự.
   - Lỗi encoding (ký tự không giải mã được).
   - Ký tự lạ chiếm tỷ lệ bất thường (heuristic: > 15% ký tự ngoài phạm vi
     hợp lệ tiếng Việt/ASCII/dấu câu thông dụng).
   - Trang rỗng (0 ký tự có nghĩa sau khi strip khoảng trắng).

   Khi fallback được kích hoạt, OCR chạy cho **toàn bộ file** (theo đúng
   hành vi của `client.parsing.parse`), không chỉ riêng trang lỗi.
4. **Chuẩn hoá Unicode NFC** (`unicodedata.normalize("NFC", text)`) cho toàn
   bộ text, dù lấy từ PyMuPDF hay từ OCR.
5. **Lưu raw text** vào `output/raw/<ten_pdf>.json`, gồm text theo từng
   trang + metadata: `source` (tên file), `page`, `ocr_used` (bool),
   `language` ("vi").
6. **Chunking**: từ raw text, sinh chunk theo cả ba chiến lược, ghi kết quả
   vào `output/chunks/<ten_pdf>_<strategy>.json`.

## 4. Ba chiến lược chunking

| Chiến lược | Nguyên tắc cắt | Tham số chính |
|---|---|---|
| **Fixed-size** | Cắt theo số ký tự cố định, có overlap giữa các chunk liên tiếp | `chunk_size` (mặc định 800 ký tự), `overlap` (mặc định 120 ký tự) |
| **Semantic** | Ưu tiên cắt tại ranh giới đoạn văn (dòng trống, ký tự xuống dòng kép, dấu kết đoạn); không cắt giữa câu nếu tránh được | `max_chunk_size` (mặc định 1000 ký tự) làm giới hạn mềm — gộp đoạn liền kề tới khi gần đạt giới hạn |
| **Hierarchical** | Dò các mốc cấu trúc theo 5 cấp Chương/Mục/Điều/Khoản/Điểm; mỗi mốc là điểm bắt đầu 1 chunk mới | Không có giới hạn kích thước cứng; nếu PDF không có cấu trúc rõ, toàn bộ text là 1 chunk kèm cảnh báo `structure_detected: false` |

**Cách nhận diện từng cấp (đã hiệu chỉnh sau khi test trên văn bản luật thật —
xem `REVIEW_buoi_05.md` mục "Vòng review 2"):**
- Chương/Mục/Điều: bắt tại **đầu dòng**, đúng từ khoá ("Chương I", "Mục 1",
  "Điều 5."); Điều bắt buộc có dấu chấm ngay sau số để phân biệt tiêu đề thật
  với câu trích dẫn chéo kiểu "...theo Điều 5 Thông tư này".
- Khoản/Điểm: văn bản luật thật **không** viết tường minh chữ "Khoản"/"Điểm" ở
  đầu mục — chỉ đánh số/chữ cái trần ("1.", "a)"). Vì vậy hai cấp này được
  nhận diện qua **định dạng liệt kê ở đầu dòng** ("<số>. " và "<chữ>) "), không
  dựa vào từ khoá. Nhãn hiển thị "Khoản 1"/"Điểm a)" là do code tự gắn thêm
  cho dễ đọc — đây không phải bịa cấu trúc vì bản thân số/chữ cái đánh dấu là
  có thật trong văn bản, chỉ đặt tên cấp theo quy ước soạn thảo luật Việt Nam.

Chiến lược hierarchical **không được bịa cấu trúc**: nếu không phát hiện mốc
nào theo regex, pipeline phải ghi cảnh báo rõ ràng trong log và trong
metadata output (`structure_detected: false`), không tự suy diễn heading.

## 5. Định dạng metadata mỗi chunk

Mỗi chunk là 1 object JSON với các trường bắt buộc:

```json
{
  "chunk_id": "string, duy nhất trong phạm vi 1 file + 1 strategy",
  "strategy": "fixed_size | semantic | hierarchical",
  "source": "tên file PDF gốc",
  "page_start": "int",
  "page_end": "int",
  "text": "string, đã chuẩn hoá NFC",
  "structure_path": "string|null — chỉ có ở hierarchical, ví dụ 'Chương II > Điều 5'"
}
```

## 6. Xử lý lỗi

- Lỗi ở một trang (đọc PyMuPDF lỗi, OCR lỗi cho một phần) **không được làm
  dừng toàn bộ job** — ghi cảnh báo, đánh dấu trang đó, tiếp tục các trang
  còn lại.
- Nếu thiếu `LLAMA_CLOUD_API_KEY` mà pipeline cần fallback OCR: dừng nhánh
  OCR cho file đó, ghi cảnh báo rõ ràng, không crash toàn bộ chương trình.
- Mọi lỗi/cảnh báo được in ra console bằng tiếng Việt dễ hiểu, không in giá
  trị secret.

## 7. Giao diện dòng lệnh (CLI)

`src/pipeline.py` hỗ trợ:

- Chế độ **dry-run** (mặc định): chạy toàn bộ luồng, in thống kê, **không**
  ghi file vào `output/`.
- Cờ **`--write`**: chạy luồng và ghi kết quả thật vào `output/`.

## 8. Ràng buộc bắt buộc

- Không tạo embedding, không kết nối/lưu vector database, không gọi LLM để
  sinh sinh văn bản trong Buổi 5.
- Không ghi đè hoặc sửa PDF gốc trong `datademo/`.
- Không in, log, hay lưu giá trị `LLAMA_CLOUD_API_KEY`.
- Code ở mức demo, đơn giản, dễ đọc — không thêm framework/abstraction
  không cần thiết.
