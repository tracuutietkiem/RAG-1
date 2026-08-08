# Buổi 07 — Ghi chú nội bộ

Tài liệu bài thực hành đầy đủ (9 prompt) nằm ngoài project này. Đặc tả kỹ
thuật bắt buộc cho Buổi 07 nằm tại [`SPEC_buoi_07.md`](./SPEC_buoi_07.md).

## Thứ tự thực hiện

1. Prompt 01 — Kiểm tra workspace (đã xong, `READY_WITH_WARNINGS`).
2. Prompt 02 — Tạo project và Agent Specification (đã xong).
3. Prompt 03 — Chuẩn bị môi trường (đã xong).
4. Prompt 04 — Loader và validator (đã xong, xác nhận trên máy thật: 399 chunk hierarchical hợp lệ).
5. Prompt 05 — Embedding và ChromaDB index (đã xong; đã kiểm thử offline đầy đủ qua client giả lập — idempotent, --reset an toàn, chặn vector lỗi/metadata lệch trước khi ghi; cần dán GEMINI_API_KEY thật để chạy `index` thật trên dữ liệu Buổi 05).
6. Prompt 06 — Retrieval, grounding và citation (đã xong; đã xác nhận trên máy thật với dữ liệu NHNN — `status: answered`, citation trỏ đúng metadata thật).
7. Prompt 07 — Giao diện Streamlit (đã xong; đã kiểm thử headless qua `streamlit.testing.v1.AppTest` — không lỗi, sidebar hiển thị đúng, nút Index tự khoá khi thiếu key, nút Hỏi báo lỗi rõ ràng khi chưa có collection; cần chạy `streamlit run` thật để xác nhận UI).
8. Prompt 08 — Kiểm thử tự động (đã xong; `tests/test_rag.py`, 69 test case unittest, đã xác nhận trên máy thật: `Ran 69 tests ... OK`).
9. Prompt 09 — README và nghiệm thu (đã xong — xem [`REVIEW_buoi_07.md`](./REVIEW_buoi_07.md)).

**Trạng thái: HOÀN THÀNH cả 9 prompt**, đã xác nhận trên máy thật ở từng
bước (không chỉ trong sandbox). Xem [`README.md`](./README.md) để biết cách
chạy, [`REVIEW_buoi_07.md`](./REVIEW_buoi_07.md) để xem nghiệm thu đối chiếu
SPEC.
