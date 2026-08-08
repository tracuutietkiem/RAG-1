# Buổi 09 — Multi-query & Parent–Child Retrieval

> **Không phải tư vấn pháp lý.** Hệ thống này chỉ tra cứu và trích dẫn lại nội dung
> văn bản đã được nạp. Mọi kết quả phải được đối chiếu với văn bản gốc và quy định
> hiện hành của Agribank / Ngân hàng Nhà nước trước khi sử dụng cho công việc. Không
> dùng đầu ra của hệ thống để thay thế quy trình thẩm định hoặc ra quyết định cấp tín dụng.

---

## 1. Mục tiêu và khác biệt so với Buổi 08

Buổi 08 giải quyết bài toán **một câu hỏi → một lần tìm kiếm**. Hai điểm yếu còn lại:

| Vấn đề | Ví dụ | Buổi 09 xử lý bằng |
|---|---|---|
| Người hỏi diễn đạt khác văn bản | hỏi "cần điều kiện gì", văn bản viết "phải đáp ứng" | **Multi-query**: sinh thêm 2–3 cách hỏi rồi gộp kết quả |
| Chunk nhỏ đủ để *tìm* nhưng thiếu ngữ cảnh để *trả lời* | tìm trúng khoản 3 nhưng thiếu phần đầu Điều | **Parent–Child**: tìm bằng child nhỏ, trả về parent lớn |

Nguyên tắc gốc: **đơn vị tối ưu cho tìm kiếm khác đơn vị tối ưu cho đọc hiểu.**

Toàn bộ Buổi 08 (`rag.py`, `advanced_rag.py`) được giữ nguyên dưới dạng snapshot đã
verify SHA-256; Buổi 09 chỉ thêm `hierarchical_rag.py` chồng lên.

---

## 2. Sơ đồ pipeline

```
                  Câu hỏi gốc (Q0)
                        │
        ┌───────────────┴───────────────┐
        │   Multi-query Generator       │  1 Gemini Generation call
        │   Q0 + Q1..Qn (biến thể)      │  (mode multi_* mới có)
        └───────────────┬───────────────┘
                        │
   ┌────────────┬───────┴───────┬────────────┐
   ▼            ▼               ▼            ▼
 Q0 hybrid   Q1 hybrid      Q2 hybrid    ...          ← mỗi query 1 Embedding call
   │            │               │
   └── TẦNG 1: inner RRF (BM25 ↔ semantic) trong TỪNG query ──┘
                        │
        ┌───────────────▼───────────────┐
        │  TẦNG 2: cross-query RRF      │  gộp giữa các query
        │  → child hits xếp hạng chung  │
        └───────────────┬───────────────┘
                        │  (mode *_flat dừng ở đây, rerank child)
        ┌───────────────▼───────────────┐
        │  Child → Parent (registry)    │  parent store là source of truth
        │  Parent aggregation (RRF)     │
        │  Context budget               │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │  Cross-encoder rerank PARENT  │  cặp = (Q0, parent_text)
        │  bằng CÂU HỎI GỐC             │  KHÔNG dùng biến thể
        └───────────────┬───────────────┘
                        │
                  Evidence gate
                        │
        ┌───────────────▼───────────────┐
        │  Sinh câu trả lời + citation  │  1 Gemini Generation call
        └───────────────────────────────┘
```

---

## 3. Bốn mode

| Mode | Query | Đơn vị rerank | Đơn vị trả về | Dùng để |
|---|---|---|---|---|
| `single_flat` | Q0 | child | child | baseline, tương đương Buổi 08 |
| `multi_flat` | Q0 + biến thể | child | child | đo riêng đóng góp của multi-query |
| `single_parent` | Q0 | **parent** | parent | đo riêng đóng góp của parent expansion |
| `multi_parent` | Q0 + biến thể | **parent** | parent | mặc định, đầy đủ nhất |

Bốn mode được thiết kế để **tách bạch hai cải tiến** — nếu chỉ có `single_flat` và
`multi_parent` thì không biết cải thiện đến từ multi-query hay từ parent.

---

## 4. Cấu trúc project và `.env`

```
rag_foundation/buoi_09/
├── rag.py                  snapshot Buổi 07 (không sửa)
├── advanced_rag.py         snapshot Buổi 08 (không sửa)
├── hierarchical_rag.py     ★ toàn bộ logic Buổi 09
├── ui_helpers.py           logic giao diện, thuần Python
├── app.py                  Streamlit 5 tab
├── evaluate.py             đánh giá 4 mode, retrieval-only
├── SPEC_buoi_09.md
├── eval/questions.json     bộ câu hỏi + gold labels
├── reports/                report evaluation (JSON)
├── storage/hierarchy/      children.json / parents.json / manifest.json
└── tests/                  281 unittest, offline hoàn toàn
```

`.env` — các biến riêng của Buổi 09 (ngoài phần kế thừa Buổi 07/08):

```ini
MULTI_QUERY_COUNT=3            # số biến thể sinh thêm (1–5)
MULTI_QUERY_MAX_CHARS=300      # độ dài tối đa mỗi biến thể
MULTI_QUERY_TEMPERATURE=0.2    # thấp để biến thể bám sát câu gốc
MULTI_QUERY_ORIGINAL_WEIGHT=1.5  # Q0 nặng hơn biến thể trong cross-query RRF
MULTI_QUERY_VARIANT_WEIGHT=1.0
MULTI_QUERY_RRF_K=60
PER_QUERY_CANDIDATES=12        # số child giữ lại từ MỖI query
PARENT_MAX_CHARS=6000          # trần độ dài một parent
PARENT_SCORE_CHILD_LIMIT=3     # tối đa 3 child được tính điểm cho một parent
PARENT_RRF_K=60
PARENT_CANDIDATES=10           # số parent đưa vào rerank
FINAL_PARENT_TOP_K=3           # số parent giữ sau rerank
TOTAL_CONTEXT_MAX_CHARS=16000  # trần tổng context đưa vào prompt
```

Ràng buộc được kiểm tra lúc nạp: `FINAL_PARENT_TOP_K <= PARENT_CANDIDATES`,
`TOTAL_CONTEXT_MAX_CHARS >= PARENT_MAX_CHARS`, và hai trọng số không được đồng thời bằng 0.

**Không commit `.env` lên GitHub.** File này chứa `GEMINI_API_KEY`.

---

## 5. Build hierarchy và ý nghĩa các cảnh báo

```powershell
python hierarchical_rag.py hierarchy-audit      # chỉ phân tích, KHÔNG ghi
python hierarchical_rag.py build-hierarchy      # ghi store (atomic)
python hierarchical_rag.py hierarchy-status     # chỉ đọc
```

Cấp bậc Chương/Điều của mỗi chunk được xác định theo **thứ tự ưu tiên 4 tầng**:

| Tầng | Cách xác định | Corpus thật (399 chunk) |
|---|---|---|
| 1 | `metadata` có sẵn từ Buổi 05 | 293 |
| 2 | `heading_inferred` — dòng đầu chunk là "Điều N." | (gộp trong metadata) |
| 3 | `carried_forward` — kế thừa Điều của chunk liền trước | 21 |
| 4 | `document_fallback` — không xác định được | 85 |

Kết quả: **399 child → 45 parent**, 106 chunk mang cờ `ambiguous`.

Hai điểm cần hiểu đúng:

- **`ambiguous` không có nghĩa là sai.** Nó có nghĩa là cấp bậc được *suy ra* chứ
  không lấy từ metadata. Trích dẫn vẫn dùng được nhưng phải đối chiếu văn bản gốc —
  hệ thống đẩy cảnh báo này ra tới tận citation.
- **Carry-forward bị reset khi đổi Chương.** Không có bước này, chunk ở Chương II mà
  thiếu Điều sẽ bị gán nhầm Điều cuối cùng của Chương I — sai về mặt pháp lý. Corpus
  thật có 106 record ở Chương IV không có Điều nên đây là đường đi thường xuyên.

`hierarchy-status` trả `ready` / `stale` / `missing`. **Query không bao giờ tự build store** —
`stale` thì phải build lại thủ công, để anh biết dữ liệu vừa thay đổi.

---

## 6. Query expansion và ngân sách API

Q0 **luôn do code tạo** (chuẩn hoá NFC + strip), không bao giờ do model sinh — model
chỉ được trả về biến thể. Biến thể bị loại nếu: trùng Q0 sau chuẩn hoá, quá dài, rỗng,
`focus` sai enum, hoặc **làm mất tham chiếu pháp lý** có trong câu gốc (số Điều/Khoản/Điểm,
số hiệu văn bản, năm).

Ngân sách cho một lượt `multi_parent` hoàn chỉnh:

| Loại call | Số lượng | Ghi chú |
|---|---|---|
| Gemini **Generation** | **tối đa 2** | 1 sinh biến thể + 1 sinh câu trả lời |
| Gemini **Embedding** | N (= số query) | đếm riêng, **không** tính vào trần 2 |

Mode `single_*` chỉ tốn 1 Generation call. `insufficient_evidence` tốn 0 call sinh câu
trả lời. Lệnh `compare` **không sinh câu trả lời** và chỉ sinh biến thể 1 lần cho cả 4 mode.

Query set được cache trong process theo hash `(câu hỏi + config + model)`; **không ghi
xuống đĩa** để không lưu lại câu hỏi của người dùng.

---

## 7. Ba công thức

**Tầng 1 — Inner RRF** (kế thừa Buổi 08, gộp BM25 ↔ semantic trong *một* query):

```
rrf_score(d) = w_bm25/(RRF_K + rank_bm25(d)) + w_sem/(RRF_K + rank_sem(d))
```

**Tầng 2 — Cross-query RRF** (gộp giữa các query):

```
multi_query_rrf_score(d) = Σ  weight(q) / (MULTI_QUERY_RRF_K + rank_q(d))
                          q tìm thấy d

weight(Q0) = 1.5   weight(biến thể) = 1.0
```

Ví dụ tính tay: Q0 hạng 2, Q1 hạng 1 → `1.5/62 + 1.0/61 = 0.04058699`.

**Parent aggregation**:

```
parent_rrf_score(p) = Σ  1 / (PARENT_RRF_K + multi_query_rank(child))
                     child ∈ top PARENT_SCORE_CHILD_LIMIT của p
```

Ví dụ tính tay: child hạng 1 và 3 → `1/61 + 1/63 = 0.032266458`.

> **Cả ba công thức chỉ dùng THỨ HẠNG, không dùng điểm thô.** BM25 score, cosine
> distance và RRF score có thang đo khác nhau; cộng thẳng chúng là sai. Có unit test
> chứng minh: đổi điểm thô từ 999.0 xuống 0.00001 mà giữ nguyên hạng thì kết quả không đổi.

Cap `PARENT_SCORE_CHILD_LIMIT=3` tồn tại để một Điều dài 30 đoạn không thắng chỉ vì nó
dài. Child thứ 4 trở đi vẫn nằm trong `supporting_child_ids` để giải thích, chỉ không cộng điểm.

---

## 8. Tìm bằng child, trả về parent, rerank bằng parent

1. Mỗi child hit tra đúng **một** `parent_id` từ children registry. Store là source of
   truth — không suy đoán parent từ kết quả retrieval, không tự ghép văn bản.
2. Parent được dựng sẵn lúc build theo ranh giới child, chia window khi vượt
   `PARENT_MAX_CHARS`. **Không bao giờ cắt giữa một child**, do đó không cắt giữa khoản/điểm.
3. Context budget chỉ thêm **nguyên parent**. Nếu parent hạng 1 đã vượt trần (do child
   quá khổ — corpus thật có 2 cái), hệ thống **giữ lại kèm cảnh báo** thay vì trả context rỗng.
4. Cross-encoder chấm cặp `(CÂU HỎI GỐC, parent_text)`. **Không rerank bằng biến thể**:
   biến thể phục vụ tầng recall; đến tầng precision mà chấm bằng câu do máy tự bịa thì
   hệ thống đang tối ưu cho câu hỏi sai.
5. `parent_rerank_score = sigmoid(logit)` — **điểm chuẩn hoá của model, không phải xác
   suất câu trả lời đúng.**

Hiệu quả đo được trên corpus thật: 12 child hit (894 ký tự) → 3 parent (5.953 ký tự),
**hệ số mở rộng 6,66x**.

---

## 9. Lệnh

Tất cả chạy trong `D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_09`.

| Lệnh | Gọi API? | Tải model? |
|---|---|---|
| `python hierarchical_rag.py hierarchy-audit` | không | không |
| `python hierarchical_rag.py build-hierarchy` | không | không |
| `python hierarchical_rag.py hierarchy-status` | không | không |
| `python hierarchical_rag.py expand-query --question "..."` | **Generation ×1** | không |
| `python hierarchical_rag.py multi-child --question "..."` | Generation ×1 + Embedding ×N | không |
| `python hierarchical_rag.py parent-retrieve --mode multi_parent --question "..."` | Generation ×1 + Embedding ×N | không |
| `python hierarchical_rag.py query --mode multi_parent --question "..."` | **Generation ×2** + Embedding ×N | **có (~2,27 GB lần đầu)** |
| `python hierarchical_rag.py compare --question "..."` | Generation ×1 + Embedding ×N | có |
| `python evaluate.py --k 5` | Generation + Embedding, **không sinh câu trả lời** | có |
| `python -m streamlit run app.py` | chỉ khi bấm nút | chỉ khi bấm nút |

Chạy test (không cần mạng, không cần API key):

```powershell
cd D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG
python -m unittest discover -s rag_foundation\buoi_09\tests -t rag_foundation\buoi_09
```

---

## 10. Chọn K thế nào

| Tham số | Ý nghĩa | Tăng lên thì |
|---|---|---|
| `PER_QUERY_CANDIDATES` (12) | child giữ lại từ **mỗi** query | phủ rộng hơn, nhưng nhiễu từ biến thể vào nhiều hơn |
| `PARENT_CANDIDATES` (10) | parent đưa vào rerank | chính xác hơn, nhưng **chậm hơn tuyến tính** — cross-encoder là khâu tốn nhất |
| `FINAL_PARENT_TOP_K` (3) | parent giữ sau rerank | context dài hơn, tốn token và dễ loãng |
| `TOTAL_CONTEXT_MAX_CHARS` (16000) | trần tổng context | prompt to hơn, chậm và đắt hơn |

Quy tắc thực dụng: nới `PER_QUERY_CANDIDATES` trước (rẻ), `PARENT_CANDIDATES` sau (đắt),
`FINAL_PARENT_TOP_K` cuối cùng (ảnh hưởng chất lượng câu trả lời nhiều nhất).

---

## 11. Evaluation và giới hạn của gold labels

`evaluate.py` chạy 4 mode trên cùng bộ câu hỏi, **retrieval-only** (không sinh câu trả lời).
Chỉ số: Child Recall@K, Parent Recall@K, MRR@K, nDCG@K (relevance nhị phân), số parent/nguồn
liên quan lấy được, context chars, hệ số mở rộng, latency mean/p50, và **Generation call vs
Embedding call tách riêng**.

Ba giới hạn phải nói rõ:

1. **Toàn bộ 15 câu hỏi đang ở `needs_human_review: true`.** Nhãn được suy ra bằng quy tắc
   máy móc ("mọi chunk thuộc Điều X, trừ chunk chỉ có tiêu đề"), chưa được người có chuyên
   môn xác nhận. Số liệu chỉ để tham khảo nội bộ.
2. **Bốn câu hỏi mẫu A–D trong tài liệu Buổi 09 không áp dụng cho corpus này.** Tài liệu
   viết cho một Thông tư về *hoạt động cho vay*; corpus thực tế là văn bản về *tỷ lệ an toàn vốn*.
   Đã kiểm chứng: các cụm "không được cho vay", "điều kiện vay vốn", "cơ cấu lại thời hạn
   trả nợ" xuất hiện **0 lần**. Bốn câu này được giữ lại với `scope: out_of_scope`, không
   tính vào metric, dùng để kiểm tra hệ thống có biết trả lời "không đủ căn cứ" hay không.
3. **Câu `out_of_scope` không có nhãn nên metric trả `None`, không phải `0.0`.** Trả 0.0 sẽ
   bị đọc nhầm thành "hệ thống trượt", trong khi thực tế là "không có gì để trượt".

Nhãn trỏ tới `parent_id` không còn tồn tại trong store sẽ làm evaluator **dừng lại báo lỗi**,
không im lặng tính recall trên tập rỗng rồi báo số đẹp.

---

## 12. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `hierarchy_not_ready (stale)` | file chunk hoặc `PARENT_MAX_CHARS` đã đổi | chạy `build-hierarchy`, sau đó **resolve lại `relevant_parent_ids`** trong `eval/questions.json` |
| `hierarchy_not_ready (missing)` | chưa build lần nào | chạy `build-hierarchy` |
| `No module named 'rank_bm25'` | thiếu package (hay gặp sau khi nâng cấp Python) | `python -m pip install rank-bm25==0.2.2` |
| `reranker_unavailable` | thiếu `transformers`/`torch`, hoặc model chưa tải xong | cài theo `requirements.txt`; lần đầu tải ~2,27 GB, để chạy hết |
| Lệnh `query` treo >2 phút lần đầu | đang tải cross-encoder | bình thường; lần sau lấy từ cache. Dùng `compare` để thử rẻ hơn |
| `query_generation_unavailable` | hết hạn mức hoặc key sai | pipeline vẫn chạy với Q0. Kiểm tra `GEMINI_API_KEY` |
| `insufficient_evidence` liên tục | ngưỡng quá chặt so với corpus | tăng `PARENT_CANDIDATES`, hoặc hạ `RERANK_MIN_SCORE` — **hạ ngưỡng làm tăng rủi ro trích dẫn sai** |
| Câu trả lời dài lê thê / lạc đề | context quá lớn | giảm `FINAL_PARENT_TOP_K` hoặc `TOTAL_CONTEXT_MAX_CHARS` |
| Chậm | cross-encoder chấm `PARENT_CANDIDATES` parent | giảm `PARENT_CANDIDATES`; đặt `RERANK_DEVICE=cuda` nếu có GPU |

**Lưu ý về đo latency:** `rerank_latency_ms` ở lần chạy đầu tiên **bao gồm cả thời gian
tải model** (đã quan sát 1.947.818 ms lần đầu so với 95.619 ms lần sau). Đây là hạn chế
đã biết của cách đo hiện tại — chỉ tin con số từ lần chạy thứ hai trở đi.

---

## 13. Cam kết về phạm vi sử dụng

- Hệ thống **không** thay thế quy trình thẩm định thực tế và **không** dùng để ra quyết
  định cấp tín dụng.
- Mọi trích dẫn phải được đối chiếu với văn bản gốc và quy định hiện hành của Agribank
  và Ngân hàng Nhà nước trước khi sử dụng.
- Không nạp thông tin định danh khách hàng, số liệu tài chính nội bộ chưa công bố hoặc
  dữ liệu bảo mật vào hệ thống này.
- Điểm rerank là **điểm chuẩn hoá của mô hình**, không phải xác suất câu trả lời đúng.
  Không diễn giải nó thành mức độ tin cậy pháp lý.
