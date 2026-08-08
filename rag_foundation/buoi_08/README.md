# Buổi 08 — Advanced RAG: Hybrid Search và Reranking

Nâng cấp tầng **retrieval** của pipeline RAG đã hoàn thiện ở Buổi 07: thêm
tìm kiếm từ khoá (BM25) bên cạnh tìm kiếm ngữ nghĩa, hợp nhất hai bảng xếp
hạng bằng RRF, rồi dùng cross-encoder chấm lại từng cặp câu hỏi–đoạn văn.

Đặc tả kỹ thuật bắt buộc: [`SPEC_buoi_08.md`](./SPEC_buoi_08.md).
Tiến độ từng bước: [`buoi_08.md`](./buoi_08.md).

## 1. Buổi 08 khác Buổi 07 ở đâu

| Buổi 07 | Buổi 08 |
|---|---|
| Chỉ semantic retrieval | BM25 (từ khoá) + semantic (ngữ nghĩa) |
| Xếp hạng theo cosine distance | Hợp nhất thứ hạng bằng RRF |
| Không có tầng reranker | Cross-encoder chấm lại từng cặp query–document |
| Một danh sách evidence | Bảng trace qua lexical → semantic → fusion → rerank |
| Chỉ xem kết quả cuối | So sánh 4 retrieval mode trên cùng câu hỏi |
| Gate theo semantic distance | Gate cuối theo rerank score đã chuẩn hoá |
| Test logic RAG | Thêm Recall@K, MRR@K, nDCG@K và rank movement |

Vì sao cần BM25 bên cạnh semantic: câu hỏi kiểu "Điều 7 Khoản 2 quy định gì"
cần khớp **chính xác** con số và thuật ngữ pháp lý — chỗ này embedding hay bỏ
sót. Ngược lại, câu hỏi diễn đạt khác từ ngữ trong văn bản ("khách hàng gặp
khó khăn có được giãn nợ không") lại cần semantic. Hai cách bù trừ nhau.

## 2. Sơ đồ pipeline

```
                         ┌→ BM25 lexical candidates ───────┐
Câu hỏi → tokenize ──────┤                                  ├→ RRF fusion
                         └→ Gemini semantic candidates ────┘
                                                               ↓
                                                     Cross-encoder reranker
                                                               ↓
                                       Confidence gate → Gemini answer + citation
```

## 3. Cấu trúc project

```
rag_foundation/buoi_08/
├── SPEC_buoi_08.md      # đặc tả bắt buộc (12 mục)
├── README.md            # file này
├── buoi_08.md           # ghi chú tiến độ nội bộ
├── requirements.txt
├── .env.example / .env  # .env KHÔNG commit
├── .gitignore
├── rag.py               # bản sao semantic baseline từ Buổi 07 (không sửa logic)
├── advanced_rag.py      # BM25 + RRF + reranker + answer pipeline + CLI
├── evaluate.py          # Recall@K / MRR@K / nDCG@K + latency
├── app.py               # Streamlit dashboard 4 tab
├── eval/questions.json  # gold labels (đang needs_human_review = true)
├── tests/               # 185 test, chạy offline hoàn toàn
├── reports/             # report JSON do evaluate.py sinh ra
└── storage/             # chroma/ và huggingface/ (không commit)
```

`rag.py` dùng `Path(__file__)` nên bản sao này tự dùng `.env` và
`storage/chroma/` **riêng của Buổi 08** — không đụng dữ liệu Buổi 07.

## 4. Chuẩn bị

Dùng `.venv` sẵn có của Buổi 05, không tạo venv mới:

```
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG
.\rag_foundation\buoi_05\.venv\Scripts\python.exe -m pip install -r .\rag_foundation\buoi_08\requirements.txt
```

Sau đó copy `.env.example` thành `.env` và dán `GEMINI_API_KEY` thật vào.
**Không commit `.env`**, không dán key vào chat hay nơi công khai.

### Cảnh báo tài nguyên reranker

Model mặc định `BAAI/bge-reranker-v2-m3` **khoảng 2.2 GB**. Lần đầu chạy mode
`hybrid_rerank` sẽ tải model về `storage/huggingface/` — cần Internet, đủ
dung lượng đĩa và RAM (khuyến nghị ≥ 8 GB trống). Trên máy **chỉ có CPU**,
rerank 20 candidate có thể mất hàng chục giây tới vài phút mỗi câu hỏi. Đây
là hành vi bình thường, không phải lỗi.

Kiểm tra máy có GPU hay không bằng lệnh `status` (dòng Device setting), hoặc
đặt `RERANK_DEVICE=cpu` trong `.env` để ép CPU cho rõ ràng.

## 5. Biến cấu hình

| Biến | Ý nghĩa |
|---|---|
| `GEMINI_API_KEY` | Key Gemini. Thiếu key thì `status`/`bm25` vẫn chạy; các lệnh cần semantic sẽ báo lỗi rõ |
| `GEMINI_EMBEDDING_MODEL` / `_DIM` | Model và số chiều embedding (phải khớp giữa lúc index và lúc query) |
| `GEMINI_GENERATION_MODEL` | Model sinh câu trả lời |
| `RAG_MAX_DISTANCE` | Ngưỡng cosine distance để evidence được coi là đạt (mode `semantic`) |
| `BM25_CANDIDATES` / `SEMANTIC_CANDIDATES` | Số candidate lấy ra ở mỗi nhánh trước khi hợp nhất |
| `RRF_K` | Hằng số làm mượt trong công thức RRF (thường 60) |
| `RRF_BM25_WEIGHT` / `RRF_SEMANTIC_WEIGHT` | Trọng số mỗi nhánh; không được đồng thời bằng 0 |
| `RERANK_CANDIDATES` | Số candidate đưa vào reranker (càng nhiều càng chậm) |
| `FINAL_TOP_K` | Số evidence cuối cùng giữ lại; phải ≤ `RERANK_CANDIDATES` |
| `RERANKER_MODEL` / `_MAX_LENGTH` / `RERANK_BATCH_SIZE` | Model, độ dài cắt, kích thước lô |
| `RERANK_MIN_SCORE` | Ngưỡng accept ở mode `hybrid_rerank` (0–1) |
| `RERANK_DEVICE` | `auto` / `cpu` / `cuda` |

## 6. Lệnh chạy

Tất cả chạy bằng Python của venv Buổi 05. Ví dụ dưới dùng đường dẫn tuyệt đối
để không phụ thuộc thư mục đang đứng:

```
set PY=D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_05\.venv\Scripts\python.exe
set B8=D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_08

REM Trạng thái hệ thống (chỉ đọc, không tạo gì, không tải model)
%PY% %B8%\advanced_rag.py status --strategy hierarchical

REM Index semantic vào Chroma của Buổi 08 (cần API key, vài phút)
%PY% %B8%\advanced_rag.py prepare-semantic --strategy hierarchical

REM Từng tầng riêng lẻ (chẩn đoán)
%PY% %B8%\advanced_rag.py bm25 --strategy hierarchical --question "Điều 7 quy định gì?"
%PY% %B8%\advanced_rag.py semantic --strategy hierarchical --question "Điều 7 quy định gì?"
%PY% %B8%\advanced_rag.py hybrid --strategy hierarchical --question "Điều 7 quy định gì?"

REM Rerank (LẦN ĐẦU SẼ TẢI MODEL ~2.2 GB)
%PY% %B8%\advanced_rag.py rerank --strategy hierarchical --question "Điều 7 quy định gì?"

REM So sánh 4 mode — KHÔNG gọi generation
%PY% %B8%\advanced_rag.py compare --strategy hierarchical --question "Điều 7 quy định gì?"

REM Hỏi đáp đầy đủ — gọi generation ĐÚNG MỘT LẦN
%PY% %B8%\advanced_rag.py query --mode hybrid_rerank --strategy hierarchical --question "Điều 7 quy định gì?"

REM Test (offline hoàn toàn, không cần key, không tải model)
%PY% -m unittest discover -s %B8%\tests

REM Đánh giá retrieval (không gọi generation)
%PY% %B8%\evaluate.py --strategy hierarchical --k 5

REM Giao diện
%PY% -m streamlit run %B8%\app.py
```

## 7. Đọc hiểu các loại điểm số

| Loại | Thang đo | Chiều tốt | Ý nghĩa |
|---|---|---|---|
| BM25 score | 0 → không giới hạn | **Cao hơn tốt hơn** | Mức khớp từ khoá; phụ thuộc độ dài văn bản và độ hiếm của từ |
| Cosine distance | 0 → 2 | **Thấp hơn tốt hơn** | Khoảng cách ngữ nghĩa giữa câu hỏi và đoạn văn |
| RRF score | ~0 → nhỏ | **Cao hơn tốt hơn** | Tổng nghịch đảo thứ hạng; chỉ dùng RANK, không dùng điểm gốc |
| Rerank score | 0 → 1 | **Cao hơn tốt hơn** | Sigmoid của logit cross-encoder |

**Không loại nào trong số này là xác suất câu trả lời đúng.** Rerank score nằm
trong khoảng 0–1 nên rất dễ bị hiểu nhầm là xác suất — nó chỉ là điểm của
model đã được ép về thang 0–1.

Vì sao dùng RRF thay vì cộng điểm: BM25 score và cosine distance khác thang
đo và ngược chiều nhau; cộng trực tiếp hoặc min-max normalize rồi cộng đều
cho kết quả tuỳ tiện, đổi theo từng câu hỏi. RRF chỉ dùng thứ hạng nên ổn
định:

```
rrf_score = w_bm25 / (rrf_k + bm25_rank) + w_semantic / (rrf_k + semantic_rank)
```

## 8. Candidate K và final K

- `BM25_CANDIDATES` / `SEMANTIC_CANDIDATES`: lấy **rộng** ở bước đầu để không
  bỏ sót (recall cao).
- `RERANK_CANDIDATES`: số candidate reranker phải đọc — đây là chỗ tốn thời
  gian nhất, tăng gấp đôi thì rerank chậm gấp đôi.
- `FINAL_TOP_K`: số evidence thực sự đưa vào prompt — giữ **hẹp** để câu trả
  lời tập trung và tiết kiệm token.

Nguyên tắc: rộng ở đầu, hẹp ở cuối. Nếu union ít hơn `RERANK_CANDIDATES`,
hệ thống tự dùng `min(RERANK_CANDIDATES, union)` — đây không phải lỗi.

## 9. Bốn retrieval mode và cách gate

| Mode | Cách xếp hạng | Điều kiện accept evidence |
|---|---|---|
| `bm25` | BM25 score | Chẩn đoán: phải đạt thêm ngưỡng semantic distance |
| `semantic` | Cosine distance | `distance <= RAG_MAX_DISTANCE` |
| `hybrid` | RRF score | Chẩn đoán: phải đạt thêm ngưỡng semantic distance |
| `hybrid_rerank` | Rerank score | `rerank_score >= RERANK_MIN_SCORE` |

`bm25` và `hybrid` là mode **chẩn đoán retrieval**, không dùng raw BM25/RRF
score làm ngưỡng tin cậy tuyệt đối, vì hai thang đo đó không có mốc có ý
nghĩa chung giữa các câu hỏi.

Kết quả `query` luôn có một trong bốn trạng thái:

- `answered` — đủ căn cứ, có câu trả lời kèm trích dẫn.
- `insufficient_evidence` — không evidence nào qua gate, **không gọi** model
  sinh câu trả lời.
- `retrieval_only` — sinh câu trả lời lỗi/rỗng; vẫn trả evidence, không giả
  vờ có câu trả lời.
- `reranker_unavailable` — yêu cầu rerank nhưng model không dùng được; **không**
  trình bày kết quả RRF như thể đã rerank.

## 10. Đánh giá

`evaluate.py` chạy retrieval (không generation) cho cả 4 mode trên cùng
corpus / cùng câu hỏi / cùng `k`, rồi tính:

- **Recall@K** — tỉ lệ tài liệu liên quan lọt vào top-K.
- **MRR@K** — nghịch đảo thứ hạng của tài liệu liên quan đầu tiên.
- **nDCG@K** — có tính đến vị trí, tài liệu đúng nằm càng cao càng tốt.
- **Latency** trung bình và p50 từng mode.

### Giới hạn của gold labels

`eval/questions.json` hiện có 8 câu hỏi, **tất cả đang đánh dấu
`needs_human_review: true`** — nghĩa là nhãn "đoạn nào liên quan" do người
xây dựng bài tự gán, **chưa được chuyên gia pháp lý duyệt**. Vì vậy:

- Report luôn kèm cảnh báo và **không tuyên bố mode nào chiến thắng chính thức**.
- Cỡ mẫu 8 câu là quá nhỏ để kết luận thống kê.
- Muốn kết luận đáng tin, cần mở rộng bộ câu hỏi và có người có chuyên môn
  rà lại nhãn, sau đó mới đổi `needs_human_review` thành `false`.

Không kết luận trước rằng Hybrid hay Rerank luôn tốt hơn — phải nhìn số thực
tế. Có trường hợp reranker đẩy nhầm đoạn, hoặc BM25 thắng ở câu hỏi tra cứu
điều khoản chính xác.

## 11. Bốn câu hỏi để so sánh thủ công

**A. Tra cứu điều khoản chính xác**
```
Điều 7 quy định như thế nào về cơ cấu lại thời hạn trả nợ?
```
Quan sát: BM25 có bắt đúng "Điều 7" không? Reranker đẩy đoạn nào lên?

**B. Diễn đạt khác (paraphrase)**
```
Khách hàng gặp khó khăn có thể được điều chỉnh kỳ hạn trả nợ ra sao?
```
Quan sát: semantic có tìm được đoạn mà lexical bỏ sót không?

**C. Nhiều khái niệm cùng lúc**
```
Phân loại nợ và trích lập dự phòng được thực hiện như thế nào?
```
Quan sát: RRF có gộp được cả hai nhóm khái niệm không?

**D. Ngoài phạm vi**
```
Ngân hàng nào có lãi suất tiết kiệm cao nhất hôm nay?
```
Quan sát: gate có chặn không? Nếu vẫn `answered` thì ghi nhận là
false positive — **không sửa output thủ công**.

## 12. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Collection ... chưa tồn tại` | Chưa index semantic cho Buổi 08 | Chạy `prepare-semantic --strategy <tên>` |
| `Thiếu GEMINI_API_KEY` | `.env` chưa có key | Dán key thật vào `.env` (không commit) |
| Tải model reranker rất lâu / lỗi mạng | Model ~2.2 GB | Kiểm tra Internet, dung lượng `storage/huggingface/`; chạy lại (đã tải xong sẽ dùng cache) |
| Rerank rất chậm | Chạy trên CPU | Giảm `RERANK_CANDIDATES`, hoặc dùng máy có GPU và đặt `RERANK_DEVICE=cuda` |
| `RERANK_DEVICE=cuda nhưng máy không có CUDA` | Cấu hình sai | Đổi về `auto` hoặc `cpu` |
| Máy bị treo / hết RAM khi rerank | Model + batch quá lớn | Giảm `RERANK_BATCH_SIZE` xuống 1–2, giảm `RERANKER_MAX_LENGTH` |
| `429 RESOURCE_EXHAUSTED` | Vượt quota Gemini free tier | Đợi rồi chạy lại; index là idempotent nên không mất dữ liệu đã có |
| `metadata không khớp cấu hình` | Đổi model/dimension sau khi đã index | Chạy `prepare-semantic --reset` |

## 13. Giới hạn và lưu ý sử dụng

- **Đây không phải tư vấn pháp lý.** Kết quả chỉ là công cụ tra cứu tham
  khảo; mọi kết luận nghiệp vụ (thẩm định, cấp tín dụng, xử lý nợ) phải đối
  chiếu với văn bản gốc và quy định hiện hành của Agribank và Ngân hàng Nhà
  nước trước khi sử dụng.
- Điểm số của reranker và RRF **không phải xác suất đúng**.
- Chỉ đưa vào pipeline những tài liệu được phép gửi ra dịch vụ bên ngoài
  (Gemini). Không đưa dữ liệu khách hàng, số liệu nội bộ chưa công bố hay dữ
  liệu định danh cá nhân.
- Latency hiển thị chỉ để quan sát tương đối, không phải benchmark khoa học.
