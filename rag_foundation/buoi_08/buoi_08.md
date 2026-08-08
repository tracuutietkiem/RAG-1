# Buổi 08 — Ghi chú nội bộ

Tài liệu bài thực hành đầy đủ (10 prompt) nằm ngoài project này. Đặc tả kỹ
thuật bắt buộc cho Buổi 08 nằm tại [`SPEC_buoi_08.md`](./SPEC_buoi_08.md).

## Thứ tự thực hiện

1. Prompt 01 — Kiểm tra baseline Buổi 07 (xong, `READY`: 69 test Buổi 07 PASS, 821 record hợp lệ).
2. Prompt 02 — Tạo project và Advanced RAG Specification (xong).
3. Prompt 03 — Package và cấu hình (xong: torch 2.13.0+cpu, transformers 5.14.1, rank-bm25 0.2.2).
4. Prompt 04 — BM25 lexical retrieval (xong, 28 test).
5. Prompt 05 — Semantic candidate retrieval (xong, 53 test cộng dồn).
6. Prompt 06 — Hybrid search bằng RRF (xong, 83 test cộng dồn).
7. Prompt 07 — Cross-encoder reranker (xong, 109 test cộng dồn).
8. Prompt 08 — Advanced RAG answer pipeline (xong, 144 test cộng dồn).
9. Prompt 09 — Streamlit comparison dashboard (xong).
10. Prompt 10 — Test, evaluation, README và nghiệm thu (xong, 185 test cộng dồn).

## Trạng thái

**Code hoàn thành cả 10 bước, 185 test offline PASS.**

Phần cần chạy thật trên máy (tốn API quota / tải model), xem hướng dẫn ở
[`README.md`](./README.md) mục 6:

- `prepare-semantic` — index 399 chunk vào Chroma của Buổi 08 (cần API key).
- `rerank` / `query --mode hybrid_rerank` — lần đầu tải model ~2.2 GB.
- `evaluate.py` — cần semantic index đã sẵn sàng.

Máy hiện tại chỉ có CPU (`cuda available: False`) nên rerank sẽ chậm.
