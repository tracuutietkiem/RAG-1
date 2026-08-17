# Vi du Retrieval - Buoi 14

- top_k = 5, candidate_k = 20, RRF_K = 60
- Dense backend: `lsa` (FALLBACK - khong phai neural embedding)
- Rerank backend: `fallback_lexical_overlap` (FALLBACK - khong phai neural cross-encoder)

> Ca 4 cau hinh dung CHUNG mot corpus `data/processed/chunks_normalized.csv`.

---

## [EXACT_KEYWORD] Thông tư 01/2014/TT-NHNN Điều 72 quy định nội dung gì?

*Cau hoi chua ma van ban va so dieu cu the -> loi the cua BM25.*


**BM25-only**

| # | chunk_id | score | citation |
|---|---|---|---|
| 1 | `44209_D72_078` | 43.87486 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 2 | `169221_D1K4_006` | 29.117923 | Thông tư số 43/2024/TT-NHNN sửa đổi, bổ sung một số điều của Thông tư  |
| 3 | `44209_D43_049` | 28.753095 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 4 | `44209_D57_063` | 28.180615 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 5 | `44209_D69_075` | 27.551435 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |


**Dense-only**

| # | chunk_id | score | citation |
|---|---|---|---|
| 1 | `44209_D43_049` | 0.595432 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 2 | `44209_D46_052` | 0.567083 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 3 | `44209_D72_078` | 0.519936 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 4 | `44209_D57_063` | 0.505846 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 5 | `44209_D54_060` | 0.49003 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |


**Hybrid (RRF)**

| # | chunk_id | bm25_rank | dense_rank | rrf_score | citation |
|---|---|---|---|---|---|
| 1 | `44209_D43_049` | 3 | 1 | 0.032266 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 2 | `44209_D72_078` | 1 | 3 | 0.032266 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 3 | `44209_D57_063` | 4 | 4 | 0.031250 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 4 | `44209_D46_052` | 11 | 2 | 0.030214 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 5 | `44209_D69_075` | 5 | 10 | 0.029670 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |


**Hybrid + Rerank**

| # | chunk_id | hybrid_rank | hybrid_score | rerank_score | citation |
|---|---|---|---|---|---|
| 1 | `44209_D72_078` | 2 | 0.032266 | 1.152540 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 2 | `44209_D69_075` | 5 | 0.029670 | 0.678381 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 3 | `169221_D1K4_006` | 7 | 0.028787 | 0.678381 | Thông tư số 43/2024/TT-NHNN sửa đổi, bổ sung một số điều của Thông tư  |
| 4 | `44209_D43_049` | 1 | 0.032266 | 0.625219 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |
| 5 | `44209_D70_076` | 11 | 0.027864 | 0.625219 | Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyể |

**Nhan xet**

- Top-1: BM25 `44209_D72_078` | Dense `44209_D43_049` | Hybrid `44209_D43_049` | Hybrid+Rerank `44209_D72_078`
- BM25 va Dense CHON KHAC NHAU o vi tri #1.
- Reranking doi cho **5/5** ket qua trong top-5.

---

## [SEMANTIC] Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức cho một khách hàng?

*Cau hoi dien dat theo nghiep vu, khong chua ma van ban -> can tin hieu ngu nghia.*


**BM25-only**

| # | chunk_id | score | citation |
|---|---|---|---|
| 1 | `166170_D136K2_215` | 24.906858 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 2 | 166170_ |
| 2 | `166170_D102_180` | 24.090664 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 102 | 166170_D102_180 |
| 3 | `186888_D3Kp3_006` | 23.053048 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  |
| 4 | `186888_D30_049` | 22.79896 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  |
| 5 | `166170_D135_213` | 22.53206 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 135 | 166170_D135_213 |


**Dense-only**

| # | chunk_id | score | citation |
|---|---|---|---|
| 1 | `166170_D136K2_215` | 0.549676 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 2 | 166170_ |
| 2 | `166170_D136K6_219` | 0.447863 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 6 | 166170_ |
| 3 | `166170_D136K4_217` | 0.439421 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 4 | 166170_ |
| 4 | `166170_D136K1_214` | 0.435983 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 1 | 166170_ |
| 5 | `166170_D102_180` | 0.42313 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 102 | 166170_D102_180 |


**Hybrid (RRF)**

| # | chunk_id | bm25_rank | dense_rank | rrf_score | citation |
|---|---|---|---|---|---|
| 1 | `166170_D136K2_215` | 1 | 1 | 0.032787 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 2 | 166170_ |
| 2 | `166170_D102_180` | 2 | 5 | 0.031514 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 102 | 166170_D102_180 |
| 3 | `166170_D136K6_219` | 7 | 2 | 0.031054 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 136 khoản 6 | 166170_ |
| 4 | `186888_D30_049` | 4 | 6 | 0.030777 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  |
| 5 | `186888_D3Kp3_006` | 3 | 12 | 0.029762 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  |


**Hybrid + Rerank**

| # | chunk_id | hybrid_rank | hybrid_score | rerank_score | citation |
|---|---|---|---|---|---|
| 1 | `186888_D3Kp3_006` | 5 | 0.029762 | 0.776608 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  |
| 2 | `f69936f0-6937-11f1-a48d-29bc6b0fd706_D26K3_084` | 11 | 0.026334 | 0.670481 | Văn bản hợp nhất Nghị định số 156/2020/NĐ-CP Quy định xử phạt vi phạm  |
| 3 | `166170_D102_180` | 2 | 0.031514 | 0.633353 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 102 | 166170_D102_180 |
| 4 | `166170_D135_213` | 7 | 0.029469 | 0.622487 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 135 | 166170_D135_213 |
| 5 | `186888_D9K6_024` | 16 | 0.015152 | 0.610898 | Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của  |

**Nhan xet**

- Top-1: BM25 `166170_D136K2_215` | Dense `166170_D136K2_215` | Hybrid `166170_D136K2_215` | Hybrid+Rerank `186888_D3Kp3_006`
- BM25 va Dense chon giong nhau o vi tri #1.
- Reranking doi cho **5/5** ket qua trong top-5.

---

## [MIXED] Theo Luật Các tổ chức tín dụng 32/2024/QH15, điều kiện để được cấp giấy phép thành lập ngân hàng là gì?

*Vua co so hieu van ban vua dien dat theo noi dung.*


**BM25-only**

| # | chunk_id | score | citation |
|---|---|---|---|
| 1 | `166170_D29K4_037` | 40.409507 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 4 | 166170_D |
| 2 | `166170_D8_013` | 38.951979 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 8 | 166170_D8_013 |
| 3 | `166170_D29K2_035` | 38.283506 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 2 | 166170_D |
| 4 | `166170_D99_177` | 37.94541 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 99 | 166170_D99_177 |
| 5 | `166170_D32_041` | 37.701414 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 32 | 166170_D32_041 |


**Dense-only**

| # | chunk_id | score | citation |
|---|---|---|---|
| 1 | `166170_D99_177` | 0.693213 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 99 | 166170_D99_177 |
| 2 | `166170_D8_013` | 0.684404 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 8 | 166170_D8_013 |
| 3 | `166170_D32_041` | 0.677902 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 32 | 166170_D32_041 |
| 4 | `166170_D30_039` | 0.671778 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 30 | 166170_D30_039 |
| 5 | `166170_D29K4_037` | 0.670433 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 4 | 166170_D |


**Hybrid (RRF)**

| # | chunk_id | bm25_rank | dense_rank | rrf_score | citation |
|---|---|---|---|---|---|
| 1 | `166170_D8_013` | 2 | 2 | 0.032258 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 8 | 166170_D8_013 |
| 2 | `166170_D99_177` | 4 | 1 | 0.032018 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 99 | 166170_D99_177 |
| 3 | `166170_D29K4_037` | 1 | 5 | 0.031778 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 4 | 166170_D |
| 4 | `166170_D32_041` | 5 | 3 | 0.031258 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 32 | 166170_D32_041 |
| 5 | `166170_D210K1_298` | 7 | 7 | 0.029851 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 210 khoản 1 | 166170_ |


**Hybrid + Rerank**

| # | chunk_id | hybrid_rank | hybrid_score | rerank_score | citation |
|---|---|---|---|---|---|
| 1 | `166170_D29K3_036` | 20 | 0.013514 | 1.055379 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 3 | 166170_D |
| 2 | `166170_D29K4_037` | 3 | 0.031778 | 1.048806 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 4 | 166170_D |
| 3 | `166170_D29K1_034` | 12 | 0.014706 | 1.034563 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 1 | 166170_D |
| 4 | `166170_D29K2_035` | 9 | 0.015873 | 1.032392 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 29 khoản 2 | 166170_D |
| 5 | `166170_D34_043` | 14 | 0.014286 | 1.020990 | Luật Các tổ chức tín dụng số 32/2024/QH15 | Điều 34 | 166170_D34_043 |

**Nhan xet**

- Top-1: BM25 `166170_D29K4_037` | Dense `166170_D99_177` | Hybrid `166170_D8_013` | Hybrid+Rerank `166170_D29K3_036`
- BM25 va Dense CHON KHAC NHAU o vi tri #1.
- Reranking doi cho **5/5** ket qua trong top-5.

---

## Doc bang the nao

- `bm25_rank` / `dense_rank` = `-` nghia la ung vien do **chi xuat hien o mot retriever**. Hybrid van giu lai - day chinh la ly do dung Hybrid.
- `rrf_score` tinh tu THU HANG chu khong phai tu diem tho, nen khong can chuan hoa BM25 score va cosine ve cung thang do.
- `hybrid_rank` trong bang Rerank cho biet ung vien do dung thu may TRUOC khi rerank.