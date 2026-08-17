# Buổi 14 — Hybrid Search + Reranking + Mini Knowledge Graph

Nâng cấp RAG từ retrieval đơn lẻ lên pipeline đầy đủ, và dựng Knowledge Graph mini
cho bộ 30 văn bản quy định ngành ngân hàng — tài chính.

```
Câu hỏi
  ├──► BM25 Search ──┐
  └──► Dense Search ─┴──► Hybrid Fusion (RRF) ──► Candidate Top-N
                                                      │
                                                      ▼
                                                  Reranker
                                                      │
                                                      ▼
                                            Top-k + Citation
```

```
metadata.csv + content.csv + relationships.csv
        │
        ▼
Mini Knowledge Graph ──► Neo4j
        │
        ▼
(:VanBan)-[:CONTAINS]->(:DieuKhoan)-[:NEXT]->(:DieuKhoan)
(:VanBan)-[:THAM_CHIEU|SUA_DOI_BO_SUNG|THAY_THE_BOI]->(:VanBan)
```

---

## 1. Dữ liệu nguồn (chỉ đọc)

Đề bài giả định 3 file nằm ở `../kb+hops/`. Trên máy thực tế chúng nằm ở
`../Buổi 12/ner_kb/`. Code đọc qua biến `KB_DIR` nên **không phụ thuộc tên thư mục**:

| File | Vai trò | Số dòng |
|---|---|---|
| `metadata.csv` | metadata + citation, node `VanBan` | 30 |
| `content.csv` | `content_html` — nguồn text retrieval chính | 30 |
| `relationships.csv` | quan hệ thật cho Knowledge Graph | 226 |

**Ba file này không bị sửa, không bị ghi đè, không bị di chuyển.** Mọi dữ liệu trung
gian và output đều nằm trong `buoi_14/`.

Lưu ý: `content.csv` **không có sẵn** cột `chunk_id`/`text`. Bước chuẩn hóa phải parse
HTML rồi cắt theo **Điều** — đây là việc thật, không phải đọc cột có sẵn.

---

## 2. Cài đặt

```bash
cd buoi_14
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux/macOS

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

copy .env.example .env            # Windows   (cp .env.example .env)
```

Mở `.env` và điền `NEO4J_PASSWORD` nếu muốn chạy phần Knowledge Graph.

---

## 3. Thứ tự chạy

```bash
# Prompt 0 — kiểm tra project và dữ liệu, phải thấy "Safe to continue: YES"
python scripts/inspect_project.py

# Prompt 1 — chuẩn hóa corpus (HTML -> chunk theo Điều)
python scripts/prepare_corpus.py

# Prompt 2 — baseline BM25-only và Dense-only
python scripts/baseline_retrieval.py --query "Thông tư 01/2014/TT-NHNN Điều 72 quy định gì?" --top-k 5

# Prompt 3 — Hybrid Search bằng RRF
python scripts/hybrid_search.py --query "Ai có thẩm quyền cấp tín dụng vượt hạn mức?" --candidate-k 20 --top-k 5

# Prompt 4 — thêm Reranking, xem BEFORE / AFTER
python scripts/rerank.py --query "Ai có thẩm quyền cấp tín dụng vượt hạn mức?" --candidate-k 20 --top-k 5

# Sinh file ví dụ cho 3 loại câu hỏi x 4 cấu hình
python scripts/make_examples.py

# Prompt 5 — đánh giá 4 cấu hình
python scripts/build_questions.py
python scripts/compare_retrieval.py

# Prompt 6 — Mini Knowledge Graph (cần Neo4j đang chạy)
python scripts/load_mini_kg.py                  # MVP: VanBan + DieuKhoan
python scripts/load_mini_kg.py --with-entities  # thêm NguoiKy/CoQuan/LinhVuc/DoiTuongApDung
python scripts/load_mini_kg.py --dry-run        # chỉ dựng mô hình, không chạm Neo4j

# Prompt 7 — demo CLI thống nhất + Graph hints
python scripts/query_demo.py --query "..." --method hybrid_rerank --top-k 5

# Prompt 8 — demo Streamlit
streamlit run app.py

# Kiểm thử + validation cuối
python -m unittest discover -s tests -t .
python scripts/final_validation.py
```

### Chạy và dừng Streamlit

```bash
streamlit run app.py
```

Streamlit in ra URL thật trong terminal (thường `http://localhost:8501`, nhưng nếu
cổng bận nó sẽ đổi cổng — **dùng đúng URL terminal hiển thị**, không đoán).
Dừng app: bấm `Ctrl + C` trong terminal đang chạy.

---

## 4. Hiểu các trường kết quả

| Trường | Ý nghĩa |
|---|---|
| `rank` | thứ hạng cuối cùng của cấu hình đang chọn |
| `chunk_id` | định danh duy nhất của một Điều/khoản, dạng `<document_id>_D<điều>[K<khoản>]_<seq>` |
| `document_id` | id văn bản, khớp `metadata.id` và `content.id` |
| `citation` | `Tên văn bản \| Số ký hiệu \| Điều N \| chunk_id` — dựng từ metadata thật |
| `retrieval_score` | điểm của phương pháp đang dùng (BM25 score / cosine / RRF / rerank) |
| `bm25_rank`, `dense_rank` | thứ hạng trong từng retriever; `—` nghĩa là ứng viên **chỉ** xuất hiện ở một retriever (Hybrid vẫn giữ lại) |
| `rrf_score` | điểm fusion, tính từ **thứ hạng** chứ không phải điểm thô |
| `hybrid_rank`, `hybrid_score` | vị trí và điểm **trước** khi rerank |
| `rerank_score` | điểm của tầng rerank, tín hiệu độc lập với RRF |

Vì sao dùng RRF: BM25 score và cosine nằm ở hai thang đo hoàn toàn khác nhau, cộng
thẳng là sai. RRF chỉ dùng thứ hạng nên không cần chuẩn hóa.

---

## 5. Hai backend — đọc kỹ phần này

Dense và Reranker đều có 2 backend, chọn trong `.env`:

| | Neural (đúng chuẩn) | Fallback (offline) |
|---|---|---|
| Dense | `DENSE_BACKEND=sentence_transformers`, model `thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5` | `DENSE_BACKEND=lsa` — TF-IDF + TruncatedSVD |
| Rerank | `RERANKER_BACKEND=cross_encoder`, model `BAAI/bge-reranker-v2-m3` | `RERANKER_BACKEND=fallback` — IDF overlap + phrase/code bonus |

Mặc định là `auto`: thử neural trước, nếu **không tải được model** thì tự chuyển sang
fallback **và in cảnh báo rõ ràng** ra terminal, đồng thời ghi thẳng vào
`evaluation_report.md`, `retrieval_examples.md`, `final_validation_report.md`.

Fallback **không được gọi là** neural reranker. Nó là một hàm chấm điểm độc lập với
RRF (không phải sort lại `hybrid_score`), nhưng vẫn chỉ là lexical.

---

## 6. Một lỗi nghiệp vụ đã phát hiện và sửa

Lần chạy evaluation đầu tiên, nhóm câu hỏi `EXACT_KEYWORD` có **Hit@5 = 0**: hỏi
"73/2016/NĐ-CP Điều 100 quy định gì?" nhưng đúng Điều 100 không bao giờ vào top-5.

Nguyên nhân: một chunk "Điều 100" **không chứa số hiệu văn bản của chính nó** — số
hiệu chỉ nằm ở trang bìa. Kết quả là BM25 luôn đẩy chunk trang bìa (lặp số hiệu nhiều
lần) lên #1, còn Điều cần tìm không có tín hiệu nào nối với số hiệu.

Cách sửa: thêm cột `index_text` = `<số ký hiệu> <loại văn bản> <tiêu đề> Điều N` +
nội dung. Header chỉ gồm **metadata có thật**, không bịa, và **chỉ dùng để index** —
`text` hiển thị cho người đọc giữ nguyên.

| Cấu hình | MRR@5 trước | MRR@5 sau |
|---|---|---|
| BM25 | 0.175 | 0.623 |
| Dense (fallback LSA) | 0.203 | 0.303 |
| Hybrid | 0.267 | 0.482 |
| Hybrid + Rerank | 0.246 | 0.647 |

---

## 7. Mini Knowledge Graph

Chỉ nạp quan hệ **có căn cứ**:

| Quan hệ | Nguồn | Số lượng |
|---|---|---|
| `CONTAINS` | cấu trúc thật: chunk thuộc văn bản nào | 2.528 |
| `NEXT` | thứ tự Điều/khoản trong cùng văn bản | 2.498 |
| `THAM_CHIEU` | `relationships.csv` | 15 |
| `SUA_DOI_BO_SUNG` | `relationships.csv` | 7 |
| `THAY_THE_BOI` | `relationships.csv` | 1 |

`KY_BOI`, `BAN_HANH_BOI`, `THUOC_LINH_VUC`, `AP_DUNG_CHO` có target **không phải văn
bản** mà là người ký / cơ quan / lĩnh vực / đối tượng áp dụng. Mặc định không nạp để
giữ đúng ontology MVP; bật bằng `--with-entities` nếu muốn.

An toàn Neo4j:

- Mọi node/quan hệ đều có `lab_session = "buoi_14"` → không đụng dữ liệu buổi trước.
- Dùng `MERGE` theo `id` → chạy lại không tạo bản ghi trùng.
- **Không bao giờ** chạy `MATCH (n) DETACH DELETE n`.
- Muốn xóa riêng dữ liệu buổi 14: `python scripts/load_mini_kg.py --clean --yes`.

Nếu Neo4j chưa chạy, `kg_build_report.md` ghi `NOT RUN` kèm lý do, và toàn bộ phần
Retrieval/Streamlit vẫn hoạt động bình thường.

---

## 8. Cấu trúc thư mục

```
buoi_14/
├── config.py                      cấu hình + đọc .env, không hard-code secret
├── app.py                         Streamlit demo (Prompt 8)
├── src/
│   ├── corpus.py                  nạp corpus dùng chung cho mọi retriever
│   ├── citation.py                dựng citation từ metadata thật
│   ├── bm25_retriever.py          BM25 + tokenizer giữ mã văn bản / số điều
│   ├── dense_retriever.py         Dense, 2 backend
│   ├── hybrid_retriever.py        RRF fusion
│   ├── reranker.py                Rerank, 2 backend
│   ├── graph_hints.py             quan hệ trực tiếp từ Neo4j (1 hop)
│   └── pipeline.py                retrieve(question, method, top_k)
├── scripts/                       8 script chạy theo thứ tự ở mục 3
├── cypher/                        schema.cypher, demo_queries.cypher
├── data/processed/                chunks_normalized.csv
├── data/eval/                     questions.csv
├── cache/                         embedding cache (không ghi ra folder buổi trước)
├── outputs/                       6 báo cáo
└── tests/test_retrieval.py        17 test, không cần mạng/API key
```
