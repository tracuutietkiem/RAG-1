# Nghiệm thu Buổi 08

Đối chiếu từng mục bắt buộc trong [`SPEC_buoi_08.md`](./SPEC_buoi_08.md) và
checklist cuối của tài liệu bài thực hành.

## Files tạo/sửa

Tất cả nằm trong `rag_foundation/buoi_08/` — **không sửa file nào của Buổi
05/06/07** (đã kiểm tra bằng `git status`: chỉ `buoi_08/` là thay đổi).

| File | Trạng thái |
|---|---|
| `SPEC_buoi_08.md` | Mới — 12 mục theo yêu cầu Prompt 02 |
| `README.md` | Mới — 13 mục, đủ nội dung Prompt 10 |
| `buoi_08.md` | Mới — ghi chú tiến độ |
| `requirements.txt`, `.env.example`, `.gitignore` | Mới |
| `rag.py` | Sao chép từ `buoi_07/rag.py`, chỉ thay docstring ghi rõ nguồn — không sửa logic |
| `advanced_rag.py` | Mới — config, tokenizer, BM25, semantic, RRF, reranker, answer, compare, CLI |
| `evaluate.py` | Mới — Recall@K, MRR@K, nDCG@K, latency, report JSON |
| `app.py` | Mới — Streamlit 4 tab |
| `eval/questions.json` | Mới — 8 câu hỏi, tất cả `needs_human_review: true` |
| `tests/test_bm25.py` (28), `test_semantic.py` (25), `test_rrf.py` (30), `test_reranker.py` (26), `test_answer.py` (35), `test_evaluate.py` (41) | Mới — tổng 185 test |

## Test

Lệnh: `<PYTHON> -m unittest discover -s rag_foundation/buoi_08/tests`

**Kết quả: Ran 185 tests — OK (0 FAIL).** Xác nhận trên máy thật (Windows,
`.venv` Buổi 05) ở từng bước: 28 → 53 → 83 → 109 → 144 → 185.

Toàn bộ test chạy offline: không Internet, không gọi Gemini thật, không tải
model Hugging Face, Chroma dùng `tempfile`, không dùng `.env` thật.

## Đối chiếu SPEC

| Mục SPEC | Trạng thái | Bằng chứng |
|---|---|---|
| 1. Workspace và security | ĐẠT | Chỉ ghi trong `buoi_08/`; `.gitignore` chặn `.env`, `storage/chroma/`, `storage/huggingface/`, `reports/*.json`; không hàm nào in giá trị key |
| 2. Quan hệ Buổi 05/07 | ĐẠT | `rag.py` là bản sao có docstring ghi nguồn; không import runtime từ `buoi_07/`; dùng `.env` + storage riêng |
| 3. Data contract | ĐẠT | Dùng lại `rag.load_chunks`/`validate_chunk`; fixture 8 chunk có thuật ngữ lặp, số Điều/Khoản, cặp đồng nghĩa, 1 đoạn ngoài phạm vi |
| 4. BM25 tokenizer/retrieval | ĐẠT | NFC + casefold + regex Unicode; `"Điều 7, Khoản 2"` → `['điều','7','khoản','2']`; clamp `candidate_k`; tie-break `chunk_id`; không lọc score 0 |
| 5. Semantic candidate | ĐẠT | Dùng lại `rag.embed_query`/Chroma helper; `n_results = min(k, count)`; giữ thứ tự Chroma; không đổi distance thành similarity giả |
| 6. RRF fusion | ĐẠT | Công thức kiểm bằng số tính tay (`1/61 + 1/62 = 0.03252246`); test chứng minh raw score không lọt vào công thức; union không duplicate; tie-break 4 tầng |
| 7. Cross-encoder reranker | ĐẠT | Lazy-load, `trust_remote_code=False`, cache trong `storage/huggingface/`, `eval()` + `no_grad()`, sigmoid chống tràn, `rank_change`, lỗi → `RerankerUnavailableError` |
| 8. Final evidence và citation | ĐẠT | Evidence giữ đủ 4 tầng score, field không áp dụng = `null`; citation map bằng code; test cho LLM viết bịa "file_bia_dat.pdf trang 999" và khẳng định citation vẫn trỏ nguồn thật |
| 9. Pipeline trace | ĐẠT | 4 mode, 4 status, trace đủ counts + 6 mốc latency + `generation_called`; test bắt prompt thật để chứng minh evidence bị loại không lọt vào |
| 10. Evaluation metrics | ĐẠT | 3 metric có test tính tay; cùng corpus/query/k cho mọi mode; không generation; warning khi gold chưa duyệt; report JSON có timestamp/config/model identity; lỗi query được ghi vào `failures` |
| 11. Offline testing | ĐẠT | `unittest`, không pytest; 185 test không mạng/không model/không storage thật |
| 12. UI comparison | ĐẠT | 4 tab; kiểm bằng `streamlit.testing`: mở app không gọi `load_reranker`/`prepare_semantic`/`index_chunks`/`embed_documents`/generation lần nào |

## Checklist cuối của bài thực hành

- [x] Prompt 01–10 chạy đúng thứ tự, dừng và xác nhận sau mỗi bước
- [x] Không sửa Buổi 05–07
- [x] BM25 tokenizer giữ tiếng Việt và số Điều/Khoản
- [x] Semantic và BM25 dùng cùng corpus/strategy
- [x] RRF không cộng raw score khác thang đo
- [x] Candidate union không duplicate
- [x] Cross-encoder rerank theo cặp query–document
- [x] Không tải reranker khi import/status/test
- [x] Không fake reranker trong runtime (injection chỉ dùng trong test)
- [x] Có rank movement và latency từng stage
- [x] Final evidence giữ source/page/chunk ID và score từng tầng
- [x] Chỉ evidence accepted đi vào generation
- [x] UI có comparison table và pipeline trace
- [x] Test offline không gọi API/model hub
- [x] Evaluation dùng Recall@K, MRR@K, nDCG@K
- [x] Gold labels chưa duyệt có warning
- [x] Không coi rerank score là xác suất
- [x] Không coi kết quả là tư vấn pháp lý

## Bước đã chạy thật vs NOT RUN

| Hạng mục | Trạng thái |
|---|---|
| Compile 4 file Python | PASS (máy thật) |
| 185 unittest | PASS (máy thật) |
| BM25 trên corpus thật 399 chunk | PASS — query "Điều 7 quy định gì?" trả đúng `# Điều 7. Vốn tự có` ở hạng 1 |
| `status` read-only | PASS (máy thật) |
| `prepare-semantic` trên corpus thật | PASS — 399/399 chunk index vào Chroma của Buổi 08 |
| `hybrid` (BM25 + semantic + RRF) thật | PASS — union 37, overlap 3, latency bm25=164ms semantic=5288ms |
| `query --mode hybrid` thật (có generation) | PASS — `status: answered`, citation trỏ đúng metadata thật, gate loại đúng chunk chỉ có BM25 |
| `evaluate.py` trên dữ liệu thật | PASS — 3 mode, 10 câu hỏi, report JSON đã lưu trong `reports/` |
| `hybrid_rerank` với model thật | **NOT RUN** — người dùng chọn bỏ qua để không tải model 2.2 GB; máy chỉ có CPU (`cuda available: False`) |

Chỉ còn `hybrid_rerank` là NOT RUN. Tầng reranker đã có 26 test offline bằng
mock, nhưng **chưa từng chạy với model thật** — không được coi là đã kiểm chứng
thực tế.

### Quan sát từ lần chạy thật

Câu hỏi thử đầu tiên ("Điều 7 quy định như thế nào về cơ cấu lại thời hạn trả
nợ?") cho `status: answered` nhưng nội dung trả lời là *"không đủ căn cứ"* —
và điều đó **đúng**: văn bản này nói về tỷ lệ an toàn vốn, Điều 7 là "Vốn tự
có", hoàn toàn không có nội dung cơ cấu lại thời hạn trả nợ. Model thà nói
không biết còn hơn bịa. Bốn câu hỏi mẫu trong tài liệu bài thực hành được
viết cho một văn bản giả định khác, không khớp corpus thật.

Confidence gate hoạt động đúng: chunk `_0359` đứng **hạng 1 BM25** với điểm
cao nhất (15.67) nhưng bị **loại** vì semantic không tìm thấy nó, nên không
lọt vào prompt.

## Bảng so sánh semantic vs BM25 vs hybrid (số liệu THẬT)

Chạy `evaluate.py --strategy hierarchical --k 5 --modes bm25,semantic,hybrid`
trên corpus thật 399 chunk, 10 câu hỏi (9 in_scope + 1 out_of_scope):

| mode | Recall@5 | MRR@5 | nDCG@5 | latency TB (ms) | p50 (ms) |
|---|---:|---:|---:|---:|---:|
| bm25 | 0.3095 | 0.6852 | 0.4695 | **1.9** | **1.9** |
| semantic | **0.4215** | **0.8333** | **0.6373** | 1728.8 | 1329.6 |
| hybrid | 0.3910 | **0.8333** | 0.6371 | 1330.5 | 1326.0 |

`hybrid_rerank`: **NOT RUN** — người dùng chọn bỏ qua tầng reranker để không
phải tải model 2.2 GB trên máy chỉ có CPU.

### Đọc kết quả một cách trung thực

**Hybrid KHÔNG tốt hơn semantic thuần trong phép đo này.** Semantic thắng
Recall@5 (0.4215 so với 0.3910), hoà MRR@5, và hơn nDCG@5 đúng 0.0002 — tức
là ngang nhau. Đây là kết quả ngược với kỳ vọng thông thường "hybrid luôn tốt
hơn", và tài liệu bài thực hành đã yêu cầu rõ: *không kết luận Hybrid luôn tốt
hơn nếu metric thực tế không chứng minh điều đó*.

Giải thích khả dĩ: trên corpus này BM25 yếu hơn hẳn semantic (0.3095 so với
0.4215). RRF đang chạy với trọng số ngang nhau (`RRF_BM25_WEIGHT=1.0`,
`RRF_SEMANTIC_WEIGHT=1.0`), nên thứ hạng kém của nhánh BM25 kéo tụt kết quả
hợp nhất. Đây là giả thuyết, chưa kiểm chứng.

**Đánh đổi tốc độ rất lớn:** BM25 nhanh gấp khoảng 700 lần (1.9 ms so với
1330 ms). Phần lớn độ trễ của semantic là round-trip mạng gọi Gemini embedding
cho câu hỏi, không phải chi phí tính toán.

### Hướng thử tiếp (chưa làm)

- Giảm `RRF_BM25_WEIGHT` xuống 0.3–0.5 rồi chạy lại, xem hybrid có vượt
  semantic không.
- Tăng cỡ mẫu câu hỏi (hiện 9 câu in_scope là quá ít để kết luận thống kê).
- Chạy `hybrid_rerank` khi có máy GPU để biết reranker đóng góp bao nhiêu.

### Giới hạn của bộ nhãn này

Gold labels do agent sinh bằng quy tắc máy móc **"toàn bộ chunk thuộc Điều
tương ứng, trừ chunk chỉ có tiêu đề"** — chọn quy tắc cơ học để tránh thiên vị,
nhưng hệ quả là:

- Nhãn khá rộng: có câu tới 19 chunk gold, nên Recall@5 tối đa chỉ đạt
  5/19 ≈ 0.26. Con số tuyệt đối vì thế thấp một cách giả tạo.
- Vì mọi mode đối mặt **cùng một bộ nhãn**, so sánh tương đối giữa các mode
  vẫn công bằng; chỉ có giá trị tuyệt đối là không nên diễn giải.
- Toàn bộ 10 câu vẫn ở `needs_human_review: true` — **người dùng chưa duyệt
  nhãn**. Không được dùng bảng này để tuyên bố mode nào thắng chính thức.

## Giới hạn và tài nguyên

- Máy hiện tại: CPU only (`torch 2.13.0+cpu`, `cuda available: False`).
  Rerank 20 candidate sẽ mất hàng chục giây tới vài phút mỗi câu hỏi.
- Model reranker ~2.2 GB, tải về `storage/huggingface/` ở lần chạy rerank đầu.
- Gold labels: 8 câu hỏi, tất cả `needs_human_review: true`, cỡ mẫu quá nhỏ
  để kết luận thống kê. Không tuyên bố mode nào thắng.
- Kết quả không phải tư vấn pháp lý.

## Xác nhận không sửa Buổi 05–07

`git status` trên repo chỉ hiện thay đổi trong `rag_foundation/buoi_08/`.
Ngoại lệ duy nhất đã được ghi rõ từ Buổi 07: `buoi_05/.venv/` được cài thêm
package theo `buoi_08/requirements.txt` (đúng như tài liệu cho phép).
