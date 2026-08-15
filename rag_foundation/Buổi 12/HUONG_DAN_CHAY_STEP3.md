# Hướng dẫn chạy BƯỚC 3 (Gemini) trên máy của bạn

Sandbox xử lý dữ liệu trên cloud của tôi bị chặn truy cập ra Internet tới
`generativelanguage.googleapis.com` (chỉ được phép gọi tới một số domain rất giới hạn
như PyPI/npm). Vì vậy script gọi Gemini API cần được BẠN chạy trực tiếp trên máy tính
của mình (có Internet bình thường), không chạy được từ sandbox của tôi.

## Các bước

1. Mở terminal/PowerShell, vào thư mục dự án:
   ```
   cd "D:\01_CONG_VIEC\phan_mem_tra_cuVB\Buổi 12"
   ```

2. Tạo virtual environment (nếu chưa có) và cài thư viện:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements_step3.txt
   ```

3. Kiểm tra file `.env` trong thư mục này đã có `GEMINI_API_KEY` (đã có sẵn, dùng lại
   key từ buổi 11).

4. Đảm bảo đã có `ner_kb\cleaned_documents.csv` (kết quả BƯỚC 1 — đã có sẵn trong
   thư mục `ner_kb`).

5. Chạy:
   ```
   python step3_gemini_extraction.py
   ```

6. Script sẽ tự tạo:
   - `ner_kb\extracted_entities_raw.csv`
   - `ner_kb\enriched_metadata.csv`
   - Nếu có lỗi gọi API cho document nào, log lỗi vào `loi_buoc3_gemini.txt`
     (KHÔNG dừng cả batch).

7. Chạy xong, gửi lại cho tôi 2 file CSV output (kéo thả vào chat hoặc cho tôi biết
   đường dẫn) để tôi tiếp tục kiểm tra và làm BƯỚC 4.

## Lưu ý an toàn

- Script không in `GEMINI_API_KEY` ra terminal.
- Script không sửa `metadata.csv`, `content.csv`, `cleaned_documents.csv`.
- Mỗi entity đều được kiểm tra evidence phải thực sự xuất hiện trong văn bản
  trước khi được giữ lại (chống hallucination).
