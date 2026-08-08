# Review Buổi 5 — Đối chiếu code với SPEC_buoi_05.md

## 1. Checklist nghiệp vụ (đối chiếu SPEC mục 3, 6, 8)

| # | Hạng mục | Kết quả | Ghi chú |
|---|---|---|---|
| 1 | Llamaparse có đang được gọi khi cần | PASS | `ocr_reader.read_pdf` gọi `ocr_pdf_via_llamaparse` khi có trang lỗi |
| 2 | PDF có text layer tốt tránh OCR không cần thiết | PASS | Chỉ fallback khi ≥1 trang bị `detect_page_error` đánh dấu lỗi |
| 3 | OCR chạy khi text layer lỗi (font/encoding/ký tự lạ/rỗng) | PASS | Test thực tế trên PDF mẫu: 74/74 trang bị phát hiện lỗi font → kích hoạt fallback |
| 4 | Unicode tiếng Việt chuẩn hoá NFC | PASS | `normalize_nfc()` áp dụng cho mọi trang trước khi lưu |
| 5 | Fixed-size có overlap hợp lý | PASS | Mặc định 120/800 ký tự (~15%), validate `overlap < chunk_size` |
| 6 | Semantic không cắt giữa câu khi có thể | PASS (có giới hạn) | Cắt theo ranh giới đoạn văn; **giới hạn đã biết**: nếu 1 đoạn văn tự nó dài hơn `max_chunk_size`, đoạn đó vẫn giữ nguyên thành 1 chunk (ưu tiên không cắt giữa câu hơn là bám sát kích thước) |
| 7 | Hierarchical không bịa cấu trúc | PASS | Khi không tìm thấy mốc Chương/Mục/Điều/Khoản/Điểm → trả 1 chunk + `structure_detected: false`, không tự suy diễn heading (xác nhận bằng test) |
| 8 | Lỗi 1 trang không làm dừng job | PASS | Try/except quanh từng trang trong `_read_pymupdf_pages`; test `trang rỗng` xác nhận không crash |
| 9 | PDF gốc không bị ghi/sửa | PASS | So khớp MD5 trước/sau xử lý: `279e72e590d158daeb8bb9f94b8368ff` (khớp) |
| 10 | Secret (API key) không bị log/in/ghi | PASS | `grep` toàn bộ `output/` và `src/*.py` không thấy giá trị key; lỗi thiếu key chỉ báo tên biến, không in giá trị |
| 11 | Không tạo embedding / vector DB / gọi LLM | PASS | Không có import liên quan trong toàn bộ `src/` |

## 2. Bảng test (`tests/test_pipeline.py`)

| Input | Expected | Actual | Kết quả |
|---|---|---|---|
| `normalize_nfc("Điện")` | Chuỗi NFC chuẩn | Khớp `unicodedata.normalize("NFC", ...)` | PASS |
| `normalize_nfc(None)` | Không crash, trả `""` | `""` | PASS |
| `detect_page_error("")` | `is_error=True`, lý do "rỗng" | Đúng | PASS |
| `detect_page_error(<văn bản tiếng Việt chuẩn>)` | `is_error=False` | Đúng | PASS |
| `detect_page_error(<text mất dấu bất thường>)` | `is_error=True` | Đúng | PASS |
| `fixed_size_chunks` trên 1500 ký tự, `chunk_size=400, overlap=50` | ≥3 chunk, `chunk_id` duy nhất, `page_start<=page_end` | Đúng | PASS |
| `fixed_size_chunks` với `overlap>=chunk_size` | Raise `ValueError` | Đúng | PASS |
| `semantic_chunks` trên 3 đoạn văn | ≥1 chunk, không chunk rỗng | Đúng | PASS |
| `hierarchical_chunks` trên text không cấu trúc | 1 chunk, `structure_detected=False`, `structure_path=None` | Đúng | PASS |
| `hierarchical_chunks` trên text có Chương/Điều | 5 chunk, `structure_path` lồng đúng (vd `"Chương I > Điều 1"`) | Đúng | PASS |
| `*_chunks` trên toàn trang rỗng | Trả `[]`, không crash | Đúng | PASS |
| `ocr_pdf_via_llamaparse` khi thiếu key | Raise `OcrUnavailableError`, không lộ giá trị key | Đúng | PASS |
| `read_pdf` trên PDF mẫu thật (74 trang) | Không crash, trả đủ số trang, fallback OCR được thử rồi lùi về PyMuPDF khi thiếu key | Đúng | PASS |

**Tổng: 24/24 test PASS** (chạy `python tests/test_pipeline.py`).

## 3. Lỗi đã sửa trong quá trình review

1. **Hierarchical chèn placeholder "…" khi thiếu cấp trung gian** (vd văn bản có Chương → Điều nhưng không có Mục) khiến `structure_path` sai thành `"Chương I > … > Điều 1"`. → Sửa `hierarchical_chunks` trong `src/chunking.py`: dùng `dict[level, label]` thay vì list cố định vị trí, chỉ nối các cấp thực sự xuất hiện. Đã xác nhận lại bằng test, `structure_path` nay đúng `"Chương I > Điều 1"`.

## 4. Kết quả chạy thật trên PDF mẫu (`2026-08-01_TaiLieu_NHNNSigned.pdf`, 74 trang)

| Chiến lược | Số chunk | Độ dài min | Độ dài max | Độ dài trung bình |
|---|---|---|---|---|
| fixed_size | 214 | 249 | 800 | 797 |
| semantic | 73 | 464 | 2 770 | 1 984 |
| hierarchical | 1 | 145 084 | 145 084 | 145 084 |

Ghi chú: PDF gốc dùng font tiếng Việt cũ, PyMuPDF trích ra text mất dấu hoàn toàn
(vd "NGAN HANG NHA. mroc VI:E:TNAM" thay vì "NGÂN HÀNG NHÀ NƯỚC VIỆT NAM") — đây
chính là ca lỗi font/encoding mà SPEC yêu cầu phát hiện. Pipeline phát hiện đúng
74/74 trang lỗi, thử fallback OCR qua LlamaParse, và báo lỗi rõ ràng vì `.env`
mới ở dạng placeholder. Chiến lược hierarchical vì vậy không tìm thấy mốc
"Điều/Khoản" hợp lệ (do mất dấu) và đúng theo SPEC đã trả về 1 chunk với
`structure_detected: false` thay vì bịa cấu trúc.

**Khi anh dán `LLAMA_CLOUD_API_KEY` thật vào `src/.env` và chạy lại
`python src/pipeline.py --write`, OCR sẽ chạy thật và kỳ vọng chiến lược
hierarchical sẽ phát hiện được cấu trúc Chương/Điều/Khoản của Thông tư.**

## 5. Vòng review 2 — sau khi chạy OCR thật với key của anh

Anh đã dán `LLAMA_CLOUD_API_KEY` thật và chạy `python src/pipeline.py --write`.
OCR chạy thành công (`ocr_fallback_triggered: true`), text OCR ra đúng tiếng
Việt có dấu (vd `"# NGÂN HÀNG NHÀ NƯỚC VIỆT NAM"`, `"## Điều 1. Phạm vi điều
chỉnh..."`). Thống kê lần đầu:

| Chiến lược | Số chunk | Min | Max | Trung bình |
|---|---|---|---|---|
| fixed_size | 259 | 596 | 800 | 799 |
| semantic | 164 | **2** | 7 713 | 1 071 |
| hierarchical | 136 | **7** | 52 906 | 1 286 |

Kiểm tra sâu phát hiện 2 lỗi thật:

1. **Hierarchical bắt nhầm trích dẫn chéo thành mốc mới.** Văn bản luật liên
   tục có câu kiểu *"...trừ các đối tác quy định tại khoản 7 Điều này"* —
   regex cũ khớp cụm "khoản 7" ở BẤT KỲ đâu trong câu, không chỉ ở đầu dòng,
   nên tưởng đó là tiêu đề mới → sinh ra chunk rác chỉ có `"khoản 4"` (7 ký
   tự). Nguyên nhân sâu hơn: văn bản luật thật không viết tường minh chữ
   "Khoản 5"/"Điểm a)" ở đầu mục, chỉ đánh số/chữ cái trần ("1.", "a)").
   → **Sửa**: Chương/Mục/Điều bắt buộc neo đầu dòng + Điều bắt buộc có dấu
   chấm sau số; Khoản/Điểm đổi sang nhận diện qua định dạng liệt kê thật ở
   đầu dòng ("1. ", "a) ") thay vì từ khoá. Xem chi tiết trong
   `src/chunking.py` (docstring phần hierarchical) và `SPEC_buoi_05.md` mục 4.
2. **Semantic tạo chunk rác 2 ký tự** do OCR tách số trang lẻ (`"11"`) thành
   1 đoạn văn riêng giữa 2 bảng. → **Sửa**: gộp mọi đoạn văn ngắn hơn 20 ký
   tự vào đoạn liền kề trước khi chunk (`_merge_tiny_paragraphs`).

**Kết quả sau khi sửa** (chạy lại chunking trên đúng dữ liệu OCR đã có, không
cần gọi lại LlamaParse — đỡ tốn phí):

| Chiến lược | Số chunk | Min | Max | Trung bình |
|---|---|---|---|---|
| fixed_size | 259 | 596 | 800 | 799 |
| semantic | 163 | 91 | 7 713 | 1 077 |
| hierarchical | 399 | 12 | 33 047 | 437 |

Hierarchical giờ lồng đúng 5 cấp, ví dụ: `"Chương I > Điều 2 > Khoản 4 > Điểm
b)"`. Đã kiểm tra thủ công vùng từng lỗi (trang 2, Điều 2) — không còn chunk
rác, thứ tự khoản 1→7 liền mạch, đúng nội dung gốc.

Chunk lớn nhất còn lại (33 047 ký tự, `"Chương IV > Khoản 3"`, trang 31–45) là
hợp lý chứ không phải lỗi: đây là 1 khoản chứa nhiều bảng/công thức tính vốn
trải dài nhiều trang mà không có điểm a)/b) để chia nhỏ tiếp — đúng tinh thần
"không bịa cấu trúc" khi văn bản gốc không có mốc chi tiết hơn.

Bộ test đã cập nhật theo quy ước mới (26/26 PASS), bao gồm 1 test riêng xác
nhận câu trích dẫn chéo "khoản 1 Điều 1" trong văn bản KHÔNG bị coi là mốc mới.
