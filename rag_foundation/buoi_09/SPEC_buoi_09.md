# SPEC — Buổi 09: Multi-query Retrieval và Parent–Child Retrieval

Tài liệu quy chiếu bắt buộc cho toàn bộ Buổi 09. Mọi prompt tiếp theo phải đọc
file này trước khi sửa code.

## 1. Mục tiêu và khác biệt Buổi 08/09

Buổi 08 đã có Advanced RAG: BM25 + semantic → RRF → cross-encoder rerank chunk
→ Gemini. Buổi 09 giải quyết hai hạn chế còn lại của tầng retrieval:

- **Một cách diễn đạt không bao phủ hết ý** của câu hỏi phức tạp → sinh nhiều
  truy vấn (multi-query) rồi hợp nhất.
- **Chunk nhỏ tìm tốt nhưng thiếu ngữ cảnh** để trả lời đầy đủ → tìm ở child
  nhỏ, trả về parent lớn hơn (parent–child retrieval).

| Buổi 08 | Buổi 09 |
|---|---|
| Một câu hỏi → một luồng retrieval | Một câu hỏi → Q0 + nhiều query variant |
| Một tầng RRF (BM25 ↔ semantic) | **Hai tầng RRF**: inner (BM25↔semantic) + cross-query |
| Candidate là chunk phẳng | Candidate có quan hệ child → parent |
| Rerank chunk nhỏ | Rerank **parent context** bằng câu hỏi gốc |
| Evidence là chunk tìm được | Evidence là parent + anchor child dẫn tới parent |
| 4 mode bm25/semantic/hybrid/hybrid_rerank | 4 mode single/multi × flat/parent |

Buổi 09 **không xây lại** BM25, semantic, inner RRF hay cross-encoder. Các
thành phần đó kế thừa từ snapshot Buổi 08 (`rag.py`, `advanced_rag.py`).

## 2. Sơ đồ pipeline

```
Câu hỏi người dùng
   │
   ├─► Q0 (nguyên văn, do CODE tạo — không nhờ LLM viết lại)
   └─► Multi-query Generator (1 Gemini Generation call)
          ├─► Q1: thuật ngữ pháp lý chính xác
          ├─► Q2: cách diễn đạt tương đương
          └─► Q3: khía cạnh còn thiếu
   │
   ▼  với TỪNG query độc lập
Hybrid retrieval (BM25 + semantic → inner RRF)   ← tái dùng Buổi 08
   │
   ▼
Cross-query RRF trên child hits                  ← TẦNG FUSION THỨ HAI
   │
   ▼
Child → Parent mapping (hierarchy registry)
   │
   ▼
Parent aggregation (parent_rrf_score)
   │
   ▼
Context budget (TOTAL_CONTEXT_MAX_CHARS)
   │
   ▼
Parent rerank bằng cross-encoder + CÂU HỎI GỐC   ← không dùng variant
   │
   ▼
Evidence gate → Gemini answer (1 Generation call) + citation [P1], [P2]
```

## 3. Bốn mode bắt buộc

| Mode | Query set | Evidence unit | Rerank input |
|---|---|---|---|
| `single_flat` | Chỉ Q0 | Child chunk | (Q0, child_text) — tương đương baseline Buổi 08 |
| `multi_flat` | Q0 + variants | Child sau cross-query RRF | (Q0, child_text) |
| `single_parent` | Chỉ Q0 | Parent mở rộng từ child hit | (Q0, parent_text) |
| `multi_parent` | Q0 + variants | Parent mở rộng từ fused child | (Q0, parent_text) |

`multi_parent` là mode mặc định. Khi so sánh, bốn mode phải dùng **cùng**
strategy (`hierarchical`), candidate limits, model identity, corpus version và
hierarchy version.

## 4. QueryVariant schema và validation

```json
{
  "original_question": "...",
  "queries": [
    {"query_id": "Q0", "text": "...", "origin": "original",  "focus": "original_intent"},
    {"query_id": "Q1", "text": "...", "origin": "generated", "focus": "exact_legal_terms"}
  ],
  "model": "...",
  "generation_latency_ms": 0.0,
  "cache_hit": false,
  "dropped_duplicate_count": 0,
  "status": "ready"
}
```

Quy tắc:

- **Q0 do code tạo** từ câu hỏi gốc sau `strip()` + NFC. Không nhờ Gemini viết
  lại Q0. Q0 luôn đứng đầu và không được đổi nội dung có nghĩa.
- Model **chỉ trả variants** theo schema tối thiểu `{"queries": [{"text", "focus"}]}`;
  code mới ghép Q0 vào đầu sau khi validate.
- Đúng **một** Generation API call sinh toàn bộ variants.
- Số generated query từ 1 đến `MULTI_QUERY_COUNT`; mỗi query sau trim/NFC không
  rỗng và không quá `MULTI_QUERY_MAX_CHARS`.
- Deduplicate bằng NFC + `casefold()` + chuẩn hoá whitespace/dấu câu; số bị loại
  ghi vào `dropped_duplicate_count`.
- `query_id` gán lại deterministic **sau** validation.
- Model trả ít query hợp lệ → dùng số còn lại, **không tạo query giả**.
- Nếu câu hỏi chứa `Điều`/`Khoản`/`Điểm`/số hiệu văn bản/năm thì **ít nhất một
  variant phải giữ nguyên** reference đó. Không bịa số Điều/Khoản mới.
- Không đưa answer/citation do model sinh vào retrieval metadata.
- API/JSON/schema lỗi → status `query_generation_unavailable`, **không** âm thầm
  chạy mode multi như thể đã có variants.

## 5. Hierarchy registry schema

```json
{
  "child_id": "...",
  "parent_id": "...",
  "source": "...",
  "page_start": 1,
  "page_end": 2,
  "text": "...",
  "structural_path": {"chapter": "…|null", "article": "…|null",
                      "clause": "…|null", "point": "…|null"},
  "resolution_method": "metadata | heading_inferred | carried_forward | document_fallback",
  "ambiguous": false,
  "warnings": []
}
```

Độ ưu tiên phân giải: (1) metadata hợp lệ của chính record → (2) heading cấp cao
rõ ràng ở **đầu** chunk → (3) carry forward chapter/article gần nhất **trong cùng
source** → (4) document fallback khi không xác định được article.

Không carry qua source khác. Không coi mọi cụm `Điều N` giữa câu là heading.
Metadata xung đột với heading, hoặc một chunk có nhiều ứng viên article không
phân giải chắc chắn → giữ quy tắc deterministic, đặt `ambiguous=true` và ghi
warning; **không tự chọn im lặng**.

## 6. ParentDocument schema

```json
{
  "parent_id": "...",
  "source": "...",
  "page_start": 1,
  "page_end": 3,
  "article_key": "...",
  "window_index": 1,
  "child_ids": ["..."],
  "text": "...",
  "char_count": 1234,
  "ambiguous_child_count": 0,
  "warnings": []
}
```

Quy tắc dựng parent:

- Parent là **article block**; chưa xác định article thì dùng document fallback
  block.
- Article quá dài → chia thành window liên tiếp **theo ranh giới child** để
  không vượt `PARENT_MAX_CHARS` khi có thể. **Không cắt giữa một child.**
- Một child thuộc **đúng một** parent window (invariant bắt buộc).
- Parent text ghép từ **text gốc** theo thứ tự; **không** dùng LLM tóm tắt.
  Không lặp child text.
- `page_start` = min, `page_end` = max của các child.
- `parent_id` ổn định: hash từ `source + article_key + window_index`. Cùng
  input/config phải cho ID giống nhau giữa các lần build.
- Child đơn lẻ dài hơn `PARENT_MAX_CHARS` → **giữ nguyên**, đánh warning
  `oversized_single_child`, không truncate nội dung pháp lý âm thầm.

## 7. MultiQueryChildHit và ParentCandidate schema

Child hit sau cross-query fusion:

```json
{
  "child_id": "...", "text": "...", "source": "...",
  "page_start": 1, "page_end": 2,
  "multi_query_rrf_score": 0.05,
  "multi_query_rank": 1,
  "support_query_count": 3,
  "support_query_ids": ["Q0", "Q1", "Q3"],
  "per_query_ranks": {"Q0": 2, "Q1": 1, "Q3": 4},
  "per_query_trace": {}
}
```

Parent candidate:

```json
{
  "parent_id": "...", "source": "...", "page_start": 1, "page_end": 3,
  "structural_path": {}, "text": "...",
  "parent_rrf_score": 0.03, "parent_rank": 1,
  "anchor_child_id": "...",
  "scoring_child_ids": ["..."],
  "supporting_child_ids": ["..."],
  "support_query_ids": ["Q0", "Q1"],
  "best_child_rank": 1,
  "ambiguous": false, "warnings": []
}
```

Sau rerank bổ sung: `parent_rerank_raw_score`, `parent_rerank_score`,
`parent_rerank_rank`, `parent_rank_change`.

## 8. Quy tắc hierarchy resolution và ambiguous warning

Nhận diện heading (rút kinh nghiệm Buổi 05):

- Heading phải neo **đầu dòng** (`^`), cho phép tiền tố `#` của Markdown.
- `Điều N` chỉ là heading khi **có dấu chấm sau số** (`Điều 7.`), để phân biệt
  với trích dẫn chéo kiểu *"quy định tại khoản 4 Điều 8 Thông tư này"*.
- Corpus thật có **26 record** chứa `Điều N` giữa câu — đây là bẫy đã xác định
  ở Bước 01, bắt buộc chặn.

Trường hợp phải đặt `ambiguous=true` + warning: metadata mâu thuẫn heading;
nhiều ứng viên article trong một chunk; phải dùng `carried_forward` hoặc
`document_fallback`.

## 9. Công thức cross-query RRF và parent aggregation

**Cross-query RRF** (tầng fusion thứ hai), với child `d`:

```
multi_query_rrf_score(d) = Σ  query_weight(q) / (MULTI_QUERY_RRF_K + rank_q(d))
                          q tìm thấy d
```

- Q0 dùng `MULTI_QUERY_ORIGINAL_WEIGHT` (mặc định 1.5)
- generated query dùng `MULTI_QUERY_VARIANT_WEIGHT` (mặc định 1.0)
- `rank_q(d)` là **inner fused rank** của child trong query q

**Parent aggregation**, với parent `p`:

```
parent_rrf_score(p) = Σ  1 / (PARENT_RRF_K + multi_query_rank(child))
                   child ∈ top PARENT_SCORE_CHILD_LIMIT của p
```

**Tuyệt đối không** cộng BM25 score, cosine distance, inner RRF score hay
rerank score vào hai công thức trên — chúng khác thang đo. Chỉ dùng **rank**.

Sort child: `multi_query_rrf_score` ↓ → `support_query_count` ↓ →
`best_query_rank` ↑ → `child_id`.

Sort parent: `parent_rrf_score` ↓ → số supporting query unique ↓ →
`best_child_rank` ↑ → `parent_id`.

## 10. Context budget và citation contract

- Parent builder đã chia theo `PARENT_MAX_CHARS`.
- Chọn parent theo rank nhưng tổng context không vượt `TOTAL_CONTEXT_MAX_CHARS`.
- Chỉ thêm **nguyên parent**; không cắt giữa parent hoặc child.
- Parent đầu tiên vượt budget do oversized child → **giữ parent đầu tiên** và
  trả warning rõ, không trả context rỗng.
- Duplicate parent không tính hai lần. Duplicate child text giữa các parent là
  **lỗi hierarchy invariant**.

Citation object:

```
evidence_id (P1, P2...), parent_id, anchor_child_id, supporting_child_ids,
source, page_start, page_end, structural_path, parent_rerank_score,
ambiguous, warnings
```

Label `[P1]` chỉ được tạo từ evidence **thật đã accepted**. LLM không được tự
tạo nguồn, trang, Điều/Khoản, parent_id hay child_id. Citation validation fail
→ không trình bày answer như thành công.

## 11. Status/failure contract

| Status | Ý nghĩa |
|---|---|
| `answered` | Đủ evidence, sinh được answer có citation |
| `insufficient_evidence` | Không evidence nào qua gate → **không** gọi Gemini answer |
| `retrieval_only` | Generation lỗi/rỗng, vẫn trả evidence |
| `hierarchy_not_ready` | Store thiếu hoặc manifest stale → **không** tự build trong query |
| `query_generation_unavailable` | Sinh variant lỗi (chỉ ảnh hưởng mode multi) |
| `multi_query_partial` | Q0 OK nhưng một/nhiều generated query lỗi |
| `reranker_unavailable` | Không load/chạy được cross-encoder, **không** silent fallback |

Q0 retrieval lỗi → toàn pipeline fail. Generated query lỗi → ghi lỗi theo query
và status `partial`, không giả vờ query đó trả zero result.

**Ngân sách API cho một lượt `multi_parent` hoàn chỉnh: tối đa 2 Gemini
*Generation* call** (1 sinh variants + 1 sinh answer). Các lần gọi Gemini
*Embedding* để embed Q0..Qn được **đếm riêng**, không nằm trong giới hạn 2.

Evidence gate: flat mode dùng gate baseline Buổi 08; parent mode chỉ nhận parent
có `parent_rerank_score >= RERANK_MIN_SCORE`. Hierarchy ambiguous **không** tự
động bị loại nhưng evidence/citation phải mang warning.

## 12. Testability và dependency injection

Điểm tiêm bắt buộc (theo đúng kiểu đã dùng ở Buổi 08):

- `query_generator_fn` — thay Gemini sinh variant
- `client_factory` / `embed_client_factory` / `generation_client_factory`
- `rerank_scorer` — thay cross-encoder
- `chunks_dir`, `persist_path`, `hierarchy_dir` — trỏ thư mục tạm

Fake deterministic **chỉ dùng trong test**, không phải runtime fallback. Toàn bộ
unittest: không Internet, không Gemini thật, không tải Hugging Face model, không
đọc `.env` thật, không sửa storage Buổi 05–08.

## 13. Evaluation metrics và acceptance criteria

So sánh 4 mode trên cùng question set / corpus identity / K:

- **Child Recall@K** (khi mode trả child hoặc có supporting children)
- **Parent Recall@K**
- **MRR@K**, **nDCG@K** (binary relevance)
- unique relevant parents/sources retrieved
- query count, child union count
- context chars, **expansion factor**
- mean/p50 latency
- query-generation call count và embedding call count **tách riêng**

Evaluation **retrieval-only**, không gọi answer generation. Không khẳng định
`multi_parent` thắng nếu nhãn còn `needs_human_review=true` hoặc metric không
ủng hộ kết luận đó.

## 14. Phạm vi ghi

Chỉ ghi trong `rag_foundation/buoi_09/`. Không sửa code/dữ liệu/storage của
Buổi 05–08. `rag.py` và `advanced_rag.py` trong Buổi 09 là **snapshot đã chốt
hash**, không sửa logic; phần mới nằm ở `hierarchical_rag.py`.

### Ghi nhận từ audit Bước 01 (dữ liệu thật, ảnh hưởng thiết kế)

| Phát hiện | Hệ quả bắt buộc |
|---|---|
| Chỉ **1** file hierarchical, 399 record, 1 source (tài liệu giả định 3 file) | Thống kê phải theo số thật |
| **106 record không có `Điều`** trong path (toàn bộ Chương IV) | Bắt buộc có nhánh `document_fallback` |
| **26 record** có `Điều N` giữa câu | Regex heading phải neo `^` + yêu cầu dấu chấm |
| Chunk dài nhất **33 047 ký tự** (gấp 5,5 lần `PARENT_MAX_CHARS`) | Phải có `oversized_single_child`, không cắt |
| Parent `Chương I > Điều 2` có **98 child**, 15 517 ký tự | Bắt buộc chia window theo ranh giới child |
| `chunk_id` đệm 4 chữ số nên lexical == numeric | Vẫn sort theo số để an toàn với dữ liệu tương lai |
| Metadata phủ tốt: **0** trường hợp thiếu metadata mà text có heading | `heading_inferred` ít dùng nhưng vẫn phải có |
