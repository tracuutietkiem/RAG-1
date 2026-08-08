# Buổi 6 — RAG với AI Agent

Demo hỏi đáp trên dữ liệu chunk đã tạo ở Buổi 5, dùng PostgreSQL (text +
metadata), ChromaDB (vector embedding) và Gemini (embedding + trả lời).

Xem đầy đủ ràng buộc/thiết kế tại [`SPEC_buoi_06.md`](./SPEC_buoi_06.md).

## Luồng dữ liệu

```text
JSON chunks (Buổi 5, chỉ đọc)
    │
    ▼
PostgreSQL (text + metadata)      [chưa có Postgres -> tự fallback SQLite: storage/local_fallback.db]
    │
    ├──────────┐
    │          │
    ▼          ▼
ChromaDB    Gemini
(embedding)    │
    │          │
    └────► Streamlit
```

## Chuẩn bị

1. Python: dùng đúng interpreter đã dùng ở Buổi 5 (`C:\Python314\python.exe`), không tạo venv mới.
2. Cài thư viện:
   ```
   C:\Python314\python.exe -m pip install -r requirements.txt
   ```
3. Copy `.env.example` thành `.env` (nếu chưa có) và điền:
   - `GEMINI_API_KEY` — lấy tại https://aistudio.google.com/apikey
   - `POSTGRES_PASSWORD` — mật khẩu user `postgres` lúc cài PostgreSQL (nếu đã cài)
4. Kiểm tra môi trường:
   ```
   C:\Python314\python.exe rag.py
   ```
   Lệnh này in ra: package đã cài, Python interpreter, trạng thái ChromaDB,
   trạng thái PostgreSQL (và hướng dẫn cài nếu chưa có — script sẽ **không**
   tự cài PostgreSQL giúp bạn).

## Chạy ứng dụng

```
C:\Python314\python.exe -m streamlit run app.py
```

1. Bấm **Index ngay** để đọc JSON từ `../buoi_05/output/chunks/`, tạo
   embedding bằng Gemini, lưu text vào PostgreSQL (hoặc SQLite cục bộ nếu
   chưa có Postgres) và lưu vector vào ChromaDB.
2. Nhập câu hỏi, chọn số lượng top-k, bấm **Hỏi**.

## Giới hạn đã biết (demo, không phải production)

- Nếu thiếu `GEMINI_API_KEY` lúc hỏi (nhưng đã index từ trước bằng key
  khác), hệ thống chuyển sang embedding fallback của ChromaDB
  (all-MiniLM-L6-v2) để vẫn tra cứu được — nhưng vector này **không cùng
  không gian ngữ nghĩa** với embedding Gemini lúc index, nên độ chính xác
  chỉ mang tính minh hoạ. Lần đầu dùng chế độ này cần tải model ONNX
  (~80MB), yêu cầu có kết nối mạng.
- Không có retry, không có logging, không có xác thực người dùng — đúng
  theo phạm vi bài thực hành.
