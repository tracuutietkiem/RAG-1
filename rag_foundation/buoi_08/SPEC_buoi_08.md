# SPEC — Buổi 08: Advanced RAG (Hybrid Search và Reranking)

Tài liệu quy chiếu bắt buộc cho toàn bộ Buổi 08. Mọi prompt tiếp theo phải đọc
file này trước khi sửa code. Dựa trên tài liệu bài thực hành gốc (10 prompt)
và kế thừa các nguyên tắc đã nghiệm thu ở `SPEC_buoi_07.md`.

## 1. Workspace và security

Vùng được đọc:
- `rag_foundation/buoi_05/output/chunks/`
- `rag_foundation/buoi_05/.venv/`
- toàn bộ `rag_foundation/buoi_07/` (source, test, README, SPEC — chỉ đọc)
- `rag_foundation/buoi_08/`

Vùng được ghi: chỉ `rag_foundation/buoi_08/`.

Không sửa: code/output Buổi 05; code, `.env`, tests, storage Buổi 06–07; PDF
gốc; `.venv` Buổi 05 (ngoại lệ duy nhất: cài package trong
`rag_foundation/buoi_08/requirements.txt` vào đúng venv này).

Bảo mật và chi phí:
- Không in hoặc hard-code API key, không in raw `.env`.
- Không commit `.env`, cache Hugging Face (`storage/huggingface/`), hay
  Chroma storage (`storage/chroma/`) — xem `.gitignore`.
- Không tải reranker khi import module, chạy `status` hoặc chạy test.
- Phải báo trước khi tải model reranker (có thể lớn, chạy CPU chậm).
- Chỉ gửi dữ liệu được phép (chunk văn bản công khai đã dùng ở Buổi 05–07)
  tới Gemini.
- Không gọi reranker score hay RRF score là xác suất đúng.

## 2. Quan hệ với Buổi 05 và Buổi 07

- Buổi 05 là nguồn chunk JSON duy nhất (`buoi_05/output/chunks/`), coi là
  black box — không OCR, không parse PDF, không chunk lại.
- Buổi 07 là **semantic baseline**: `rag_foundation/buoi_08/rag.py` là bản
  sao nguyên trạng của `rag_foundation/buoi_07/rag.py` tại thời điểm copy
  (Bước 02), có docstring ghi rõ nguồn. Buổi 08 **không import runtime trực
  tiếp** từ thư mục `buoi_07/` — mọi thứ Buổi 08 cần từ semantic pipeline đều
  lấy qua bản sao này.
- Vì bản sao dùng `Path(__file__).resolve().parent` để tính `BASE_DIR`, nó tự
  dùng `.env` và `storage/chroma/` riêng của `buoi_08/` — độc lập hoàn toàn
  với `.env`/storage thật của Buổi 07 (không đọc, không ghi, không xoá).
- `advanced_rag.py` chỉ thêm tầng mới (BM25, RRF, reranker, answer pipeline
  4 mode) bằng cách **dùng lại** các hàm public của `rag.py`
  (`load_chunks`, `load_config`, `embed_documents`, `embed_query`,
  `collection_name`, `_chroma_client`, `retrieve`, ...) — không viết lại các
  phần đã có.

## 3. Data contract

Giống Data Contract của Buổi 07 (kế thừa nguyên vẹn, không nới lỏng):

- Trường bắt buộc: `chunk_id`, `strategy`, `source`, `page_start`,
  `page_end`, `text`.
- `chunk_id`/`strategy`/`source`/`text`: string, không rỗng sau `strip()`
  (riêng `text` được phép rỗng, bị đếm `empty_text_skipped` và bỏ qua).
- `strategy` ∈ {`fixed-size`, `semantic`, `hierarchical`} (có alias
  `fixed_size` → `fixed-size` như Buổi 07).
- `page_start`, `page_end`: integer (không chấp nhận boolean) ≥ 1,
  `page_start <= page_end`.
- `chunk_id` duy nhất trong tập chunk được chọn theo từng strategy.

Fixture riêng cho Buổi 08: `tests/fixtures/chunks_advanced_sample.json` — dữ
liệu mô phỏng (không nhạy cảm), tối thiểu 8 chunk, có: thuật ngữ pháp lý lặp
lại (`cơ cấu lại thời hạn trả nợ`, `phân loại nợ và trích lập dự phòng`), số
Điều/Khoản, hai cặp diễn đạt đồng nghĩa nhưng ít từ khóa chung (để kiểm tra
semantic tìm được điều BM25 bỏ sót), và một đoạn ngoài phạm vi nghiệp vụ tín
dụng (decoy — kiểm tra BM25/semantic không xếp hạng cao nhầm).

## 4. BM25 tokenizer/retrieval contract

`tokenize_vi_legal(text)`:

1. Input phải là string (raise lỗi rõ nếu không).
2. Chuẩn hoá Unicode NFC.
3. `casefold()`.
4. Tách token bằng regex Unicode, giữ chữ tiếng Việt và số.
5. Loại khoảng trắng và dấu câu rỗng.
6. Không stemming.
7. Không tự bỏ stopword ở phiên bản đầu.
8. Cùng một hàm dùng cho cả corpus và query (không có 2 pipeline tiền xử lý
   khác nhau).

Ví dụ bắt buộc giữ token: `"Điều 7, Khoản 2"` → có `điều`, `7`, `khoản`, `2`.

BM25 index: `rank_bm25.BM25Okapi`, chỉ ở memory (corpus nhỏ), nhận danh sách
chunk đã qua `validate_chunk`/`load_chunks` của `rag.py` — không đọc JSON lần
thứ hai bằng pipeline riêng, không pickle, không database riêng.

BM25 search — input `question, chunks, candidate_k`; output mỗi candidate:

```json
{"chunk_id": "...", "text": "...", "source": "...", "page_start": 1,
 "page_end": 2, "bm25_rank": 1, "bm25_score": 4.25}
```

Quy tắc: câu hỏi rỗng hoặc không có token phải fail rõ (`DataError`);
`candidate_k = min(candidate_k, corpus_size)`; score cao hơn xếp trước;
tie-break ổn định bằng `chunk_id`; không coi BM25 score là xác suất; không
lọc candidate chỉ vì score bằng 0 (vẫn trả top-k, giữ nguyên score); không
sửa chunk nguồn.

## 5. Semantic candidate contract

Dùng lại loader, config, collection naming, Gemini embedding và Chroma
helper trong `rag.py` (bản sao Buổi 08) — không viết embedding fallback mới.

Semantic candidates — input `question, candidate_k, strategy`; output mỗi
candidate:

```json
{"chunk_id": "...", "text": "...", "source": "...", "page_start": 1,
 "page_end": 2, "semantic_rank": 1, "semantic_distance": 0.123}
```

Quy tắc: dùng đúng model/dimension đã index; validate collection
metadata/configuration (kế thừa `_verify_collection_metadata` của Buổi 07);
`n_results = min(candidate_k, collection.count())`; distance thấp hơn xếp
trước; giữ đúng thứ tự Chroma trả về; không đổi distance thành similarity
giả; giai đoạn này không generation.

`prepare-semantic`: chỉ index khi người dùng chủ động chạy; dùng Gemini
embedding thật; idempotent (`upsert` theo `chunk_id`); dùng Chroma của Buổi
08 (không đụng storage Buổi 07); thiếu API key phải fail rõ, không vector
giả.

## 6. RRF fusion contract

BM25 score và cosine distance khác thang đo — **không min-max normalize rồi
cộng trực tiếp**. Dùng rank của mỗi hệ thống.

Công thức, với mỗi chunk:

```
rrf_score = bm25_weight / (rrf_k + bm25_rank)       (nếu có bm25_rank)
          + semantic_weight / (rrf_k + semantic_rank) (nếu có semantic_rank)
```

Config: `RRF_K`, `RRF_BM25_WEIGHT`, `RRF_SEMANTIC_WEIGHT`.

Quy tắc hợp nhất:

1. Lấy `BM25_CANDIDATES` và `SEMANTIC_CANDIDATES` độc lập.
2. Union theo `chunk_id`, không duplicate.
3. Metadata cùng `chunk_id` phải nhất quán giữa 2 nhánh; mismatch phải fail.
4. Candidate chỉ xuất hiện ở một nhánh vẫn được giữ.
5. Không dùng raw BM25 score hoặc cosine distance trực tiếp trong công thức
   RRF (chỉ dùng rank).
6. Sort `rrf_score` giảm dần.
7. Tie-break theo thứ tự: rank tốt nhất giữa hai nhánh → semantic rank (nếu
   có) → BM25 rank (nếu có) → `chunk_id`.
8. Gán `fused_rank` từ 1.

Schema candidate hợp nhất:

```json
{"chunk_id": "...", "text": "...", "source": "...", "page_start": 1,
 "page_end": 2, "bm25_rank": 1, "bm25_score": 4.2,
 "semantic_rank": 3, "semantic_distance": 0.21,
 "rrf_score": 0.03, "fused_rank": 1, "matched_by": ["bm25", "semantic"]}
```

(`bm25_rank`/`bm25_score`/`semantic_rank`/`semantic_distance` là `null` khi
candidate không xuất hiện ở nhánh đó.)

Pipeline trace của hybrid result phải có: `bm25_candidate_count`,
`semantic_candidate_count`, `union_count`, `overlap_count`, `fused_count`,
config weights + `rrf_k`, và `latency_ms` cho từng giai đoạn (tokenize/BM25,
semantic, fusion) đo bằng `time.perf_counter()` — chỉ để quan sát, không
phải benchmark khoa học.

## 7. Cross-encoder reranker contract

Model mặc định: `BAAI/bge-reranker-v2-m3`, dùng
`transformers.AutoTokenizer` + `transformers.AutoModelForSequenceClassification`
+ `torch`. Không bật `trust_remote_code=True`. Không dùng model embedding
làm reranker.

Model loading:

1. Lazy-load — chỉ load khi mode `hybrid_rerank` (hoặc lệnh `rerank`) thực sự
   được gọi. Không load khi import, `status`, `bm25`, `semantic`, `hybrid`,
   hoặc chạy unittest.
2. Cache tokenizer/model một lần trong process (không load lại mỗi request).
3. Device: `auto` → cuda nếu khả dụng, ngược lại cpu; `cpu` → ép CPU;
   `cuda` → fail rõ nếu CUDA không khả dụng (không âm thầm rơi về CPU).
4. Model `.eval()`, inference trong `torch.no_grad()`.
5. Cache Hugging Face đặt tại `rag_foundation/buoi_08/storage/huggingface/`.
6. Trước lần tải đầu tiên, phải báo rõ: model có thể lớn, cần Internet/đĩa/RAM.
7. Lỗi tải model → trả `status: "reranker_unavailable"`; **không** âm thầm
   dùng kết quả RRF như thể đã rerank.

Rerank: chỉ rerank tối đa `min(RERANK_CANDIDATES, union_count)` candidate đầu
theo `fused_rank`. Corpus nhỏ hoặc câu hỏi có ít candidate vẫn phải chạy bình
thường (không lỗi vì thiếu candidate).

Input pair: `(question, candidate_text)`. Tokenize theo batch, có truncation,
padding, giới hạn `RERANKER_MAX_LENGTH`. Lấy 1 logit / pair, tạo:

- `rerank_raw_score`: logit gốc.
- `rerank_score`: `sigmoid(logit)`, trong `[0, 1]` — chỉ là score đã chuẩn
  hoá của model, **không phải xác suất đúng**.

Sort: `rerank_score` giảm dần → `fused_rank` tăng dần → `chunk_id`. Thêm
`rerank_rank`, `rank_change = fused_rank - rerank_rank`, `reranker_model`,
`rerank_latency_ms`. Chỉ lấy `FINAL_TOP_K` sau rerank.

Injection: hàm rerank phải nhận optional callable (`reranker_factory` hoặc
tương đương) để test có thể tiêm fake reranker — fake reranker chỉ dùng
trong test, không phải runtime fallback thật.

## 8. Final evidence và citation contract

Mỗi evidence cuối cùng giữ đầy đủ: `source`/`page`/`chunk_id`/`text`, BM25
rank/score, semantic rank/distance, RRF score/fused rank, rerank raw/
normalized score, rerank rank/rank change, `accepted`. Field không áp dụng ở
mode/giai đoạn đó dùng `null`, không bịa giá trị.

Citation kế thừa nguyên tắc Buổi 07: chỉ evidence `accepted` được đưa vào
prompt sinh câu trả lời; context bao bởi delimiter rõ ràng và ghi chú đây là
dữ liệu (không phải instruction); LLM chỉ được tạo label dạng `[E1]`, `[E2]`;
code (không phải LLM) map label → metadata thật; label không hợp lệ bị loại
khỏi answer và ghi cảnh báo vào `warnings`, không bao giờ trở thành citation
giả.

## 9. Pipeline trace contract

4 mode: `bm25`, `semantic`, `hybrid`, `hybrid_rerank` (mặc định cho Advanced
RAG answer).

Gating:
- `semantic`: dùng confidence gate cosine của Buổi 07 (`RAG_MAX_DISTANCE`).
- `hybrid_rerank`: evidence `accepted` khi `rerank_score >= RERANK_MIN_SCORE`.
- `bm25`, `hybrid`: mode chẩn đoán retrieval, không dùng raw BM25/RRF score
  làm confidence tuyệt đối; nếu có gọi generation ở 2 mode này, bắt buộc có
  ít nhất một candidate cũng đạt semantic distance gate.
- Không gọi reranker score hay RRF score là xác suất.

`answer()` luôn trả đủ field:

```json
{"status": "answered | insufficient_evidence | retrieval_only | reranker_unavailable",
 "mode": "hybrid_rerank", "question": "...", "answer": "...",
 "evidence": [...], "citations": [...], "warnings": [...],
 "trace": {"bm25_candidates": 20, "semantic_candidates": 20, "overlap": 8,
           "union": 32, "reranked": 20, "accepted": 4,
           "generation_called": true,
           "latency_ms": {"bm25": 0.0, "semantic": 0.0, "fusion": 0.0,
                          "rerank": 0.0, "generation": 0.0, "total": 0.0}}}
```

Quy tắc generation: chỉ evidence accepted vào prompt; generation lỗi/rỗng →
`retrieval_only` (vẫn trả evidence); không evidence accepted →
`insufficient_evidence` (không gọi generation); reranker được yêu cầu
(`hybrid_rerank`) nhưng unavailable → `reranker_unavailable` (không nói kết
quả RRF là đã rerank).

`compare()`: chạy cùng câu hỏi qua 4 mode nhưng **không** gọi generation 4
lần (chỉ retrieval/rerank, trả bảng so sánh rank/latency). Chỉ lệnh `query`
mới gọi generation, và tối đa **một lần**.

## 10. Evaluation metrics contract

Input: `eval/questions.json`, danh sách retrieval mode, strategy, `k`.

Metrics: Recall@K, MRR@K, nDCG@K (binary relevance theo `relevant_chunk_ids`),
latency mean và p50.

Quy tắc: công thức metric phải có unit test với ranking nhỏ tính tay được;
cùng corpus/query/`k` cho mọi mode (so sánh công bằng); không gọi generation;
nếu bất kỳ gold label nào còn `needs_human_review: true` (mặc định của Buổi
08 là tất cả), report phải có warning và **không tuyên bố mode nào chiến
thắng chính thức**; report lưu JSON trong `reports/` kèm timestamp, config,
model identity; lỗi một query phải ghi fail rõ, không bỏ âm thầm.

## 11. Offline testing contract

`unittest` (không `pytest`); không Internet; không gọi Gemini thật; không
tải Hugging Face model thật; fake deterministic embedding/reranker chỉ dùng
trong test (qua injection); Chroma dùng thư mục tạm (`tempfile`), không đụng
`storage/chroma/` thật; không dùng `.env` thật.

Nhóm test bắt buộc tối thiểu (chi tiết ở Prompt 04–10, tổng ≥ 30 case):
Tokenizer/BM25 (NFC/casefold, giữ Điều/Khoản, exact match ranking, empty
query, candidate limit/tie-break); Semantic (candidate top-k/order/metadata,
collection mismatch, không vector fallback); RRF (công thức, union/overlap/
de-duplicate, missing-branch contribution, metadata mismatch, deterministic
ordering); Reranker (lazy load + injection, pair construction/batching, raw/
sigmoid score, reorder/tie-break/rank movement, candidate/final limits,
failure không silent fallback); Advanced answer (mode validation, gate theo
semantic/rerank, rejected context không vào prompt, citation thật/label giả,
retrieval-only/insufficient/reranker-unavailable, generation tối đa một lần,
compare không generation, trace schema/counts); Isolation/UI helpers (config
hoạt động khác cwd, status không tạo resource, không tải model khi import/
test).

## 12. UI comparison contract

4 tab: "Hỏi đáp Advanced RAG", "So sánh Retrieval", "Pipeline Trace",
"Đánh giá". UI chỉ gọi public function từ `rag.py`/`advanced_rag.py`, không
duplicate logic retrieval trong `app.py`.

Sidebar hiển thị: strategy, retrieval mode, final top-k, BM25/semantic
candidate K, RRF k và weights, reranker model/device/cache status, rerank
candidate K và min score, semantic collection/count, API key Có/Thiếu —
không hiển thị secret.

Tab so sánh chạy cùng câu hỏi qua BM25/Semantic/Hybrid RRF/Hybrid+Rerank,
không gọi generation, hiển thị bảng rank/rank movement chung.

Tab Pipeline Trace hiển thị latency từng giai đoạn + chú thích chiều tốt của
từng loại score (BM25 cao hơn tốt hơn; cosine distance thấp hơn tốt hơn;
RRF/rerank score cao hơn tốt hơn; rerank score không phải xác suất).

Tab Đánh giá chỉ đọc report JSON có sẵn trong `reports/` (không tự chạy
đánh giá hàng loạt khi mở trang), cảnh báo nếu gold còn
`needs_human_review=true`, không kết luận winner khi chưa có report hợp lệ.

State/cache: cache BM25 corpus theo strategy; cache reranker resource một
lần; không cache API key; session state giữ query/result gần nhất; đổi
config/strategy phải làm mới đúng cache liên quan.

Error handling: không hiện stack trace/secret; thiếu semantic index thì
hướng dẫn chạy `prepare-semantic`; thiếu reranker cache thì hướng dẫn tải khi
người dùng chủ động; không tự index hoặc tải model lúc mở app.
