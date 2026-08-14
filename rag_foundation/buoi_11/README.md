# Buổi 11 — Multi-hop Graph RAG + Hỏi đáp bằng Gemini API

> **Không phải tư vấn pháp lý.** Hệ thống chỉ tra cứu và trích dẫn lại nội dung
> đã nạp trong Neo4j từ Buổi 10 (dữ liệu phái sinh từ OCR, có thể còn lỗi nhận
> dạng). Phải đối chiếu văn bản gốc và quy định hiện hành của Agribank / Ngân
> hàng Nhà nước trước khi dùng cho công việc thật. Không dùng để thay thế thẩm
> định hoặc ra quyết định cấp tín dụng.

## Trạng thái hiện tại

| Bước | Trạng thái |
|---|---|
| Kết nối Neo4j `kb-hops` | Code xong, dùng lại dữ liệu đã nạp ở Buổi 10 |
| Vector search + multi-hop | Code xong, **chưa chạy thật** (cần tạo vector index) |
| Tích hợp Gemini API | Code xong, **chưa chạy thật** (cần `GEMINI_API_KEY`) |
| `qa_comparison.md` với 5 câu hỏi × 3 mức hops | **Chưa chạy thật** |
| Unit test | Offline hoàn toàn, không cần Neo4j/API key thật |

---

## Việc anh cần làm (theo đúng thứ tự)

### Bước A — Cài môi trường Python

```powershell
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_11
python -m venv .venv
.venv\Scripts\activate

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Trong `.env`, điền:
- `NEO4J_PASSWORD` — giống mật khẩu đã dùng ở Buổi 10.
- `GEMINI_API_KEY` — lấy tại [Google AI Studio](https://aistudio.google.com/apikey).

### Bước B — Tạo vector index (chỉ 1 lần)

```powershell
python -m src.pipeline setup-index
```

Hoặc chạy tay nội dung `setup_vector_index.cypher` trong Neo4j Browser.

### Bước C — Hỏi thử 1 câu

```powershell
python -m src.pipeline ask "Thông tư 41/2016/TT-NHNN căn cứ vào luật nào?" --hops 1
```

### Bước D — Chạy so sánh đầy đủ (5 câu hỏi × hops 0/1/2)

```powershell
python -m src.pipeline compare
```

Kết quả ghi vào `reports/qa_comparison.md`.

---

## Lưu ý quan trọng về dữ liệu

Đồ thị Neo4j hiện chỉ có **4 Document** (Thông tư 41/2016/TT-NHNN toàn văn + 3
văn bản viện dẫn dạng stub) và **3 quan hệ `CAN_CU`** — xem
`REVIEW_buoi_10.md`. Trong 5 câu hỏi kiểm thử của đề bài, **chỉ Câu hỏi 4** khớp
được với dữ liệu thật; 4 câu còn lại nên trả lời "không có đủ thông tin trong
ngữ cảnh" ở mọi mức hops — đây là hành vi ĐÚNG (chứng minh hệ thống không bịa),
không phải lỗi. Xem SPEC_buoi_11.md mục 6.

## Chạy test (offline, không cần Neo4j, không cần API key)

```powershell
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG
python -m unittest discover -s rag_foundation\buoi_11\tests -t rag_foundation\buoi_11
```

## Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `[LỖI] Chưa có vector index` | Chưa chạy Bước B | `python -m src.pipeline setup-index` |
| `GEMINI_API_KEY trống` | Chưa điền `.env` | Lấy key tại Google AI Studio, điền vào `.env` |
| `ModuleNotFoundError: No module named 'google.genai'` | Chưa cài `google-genai` | `pip install -r requirements.txt` |
| Câu trả lời luôn "không có đủ thông tin" | Đúng dự kiến cho 4/5 câu hỏi mẫu | Xem "Lưu ý quan trọng" ở trên |
| Lỗi kết nối Neo4j | Neo4j Desktop chưa Start | Mở Neo4j Desktop, Start DBMS `rag2026` (hoặc tên anh đặt) |
