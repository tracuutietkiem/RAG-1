# Bao cao danh gia Retrieval - Buoi 14

- So cau hoi: **24** (EXACT_KEYWORD=8, MIXED=8, SEMANTIC=8)
- Corpus: `data/processed/chunks_normalized.csv` (2528 chunk / 30 van ban)
- top_k = 5, candidate_k = 20, RRF_K = 60

## 0. Backend thuc te da dung (khong giau)

- Dense: `lsa` — **FALLBACK, KHONG phai neural embedding**
  - TF-IDF + TruncatedSVD(dim=256) - FALLBACK, khong phai neural | ly do fallback: ProxyError: 403 Forbidden
- Reranker: `fallback_lexical_overlap` — **FALLBACK, KHONG phai neural cross-encoder**
  - FALLBACK - IDF-weighted token coverage + phrase bonus + document-code/article bonus (KHONG phai neural cross-encoder) | ly do fallback: ProxyError: 403 Forbidden

> Ket qua duoi day phai doc kem dieu kien nay. Khi chay tren may co tai duoc
> model tu HuggingFace, dat `DENSE_BACKEND=sentence_transformers` va
> `RERANKER_BACKEND=cross_encoder` roi chay lai de co so lieu neural that.

## 1. Ket qua tong the

| Cau hinh | Hit@1 | Hit@3 | Hit@5 | MRR@5 | Dung van ban @5 |
|---|---|---|---|---|---|
| `bm25` | 0.542 | 0.625 | 0.792 | 0.623 | 0.917 |
| `dense` | 0.167 | 0.417 | 0.500 | 0.303 | 0.917 |
| `hybrid` | 0.375 | 0.583 | 0.667 | 0.482 | 0.917 |
| `hybrid_rerank` | 0.583 | 0.667 | 0.792 | 0.647 | 0.875 |

## 2. Ket qua theo loai cau hoi

### EXACT_KEYWORD

| Cau hinh | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---|---|---|---|
| `bm25` | 0.625 | 0.875 | 0.875 | 0.750 |
| `dense` | 0.000 | 0.250 | 0.250 | 0.125 |
| `hybrid` | 0.250 | 0.500 | 0.750 | 0.404 |
| `hybrid_rerank` | 0.750 | 0.875 | 0.875 | 0.812 |

### MIXED

| Cau hinh | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---|---|---|---|
| `bm25` | 0.625 | 0.625 | 0.875 | 0.681 |
| `dense` | 0.375 | 0.500 | 0.500 | 0.438 |
| `hybrid` | 0.375 | 0.625 | 0.625 | 0.479 |
| `hybrid_rerank` | 0.750 | 0.750 | 0.875 | 0.781 |

### SEMANTIC

| Cau hinh | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---|---|---|---|
| `bm25` | 0.375 | 0.375 | 0.625 | 0.438 |
| `dense` | 0.125 | 0.500 | 0.750 | 0.348 |
| `hybrid` | 0.500 | 0.625 | 0.625 | 0.562 |
| `hybrid_rerank` | 0.250 | 0.375 | 0.625 | 0.348 |

## 3. Nhan xet

- Nhom **EXACT_KEYWORD** (co so hieu van ban + so dieu): manh nhat la `hybrid_rerank` (MRR 0.812); BM25 dat MRR 0.750, Dense dat 0.125. Day dung ky vong: ma van ban la tin hieu tu khoa chinh xac, BM25 khai thac truc tiep.
- Nhom **SEMANTIC** (khong chua so hieu): manh nhat la `hybrid` (MRR 0.562); BM25 0.438, Dense 0.348.
- **Hybrid co giup khong:** Hybrid MRR 0.482 so voi BM25 0.623 va Dense 0.303.
- **Reranking co doi ranking khong:** doi vi tri #1 o **13/24** cau hoi. MRR sau rerank: 0.647.

## 4. Failure cases (khong bo query nao)

| question_id | Loai | Cau hoi | gold | Van ban dung nam trong top5? |
|---|---|---|---|---|
| Q003 | EXACT_KEYWORD | 41/2016/TT-NHNN Điều 10 quy định nội dung gì? | `117310_D10_064` | co |
| Q010 | SEMANTIC | Quy định về thay đổi vốn điều lệ được nêu ở đâu? | `168220_D13_014` | khong |
| Q011 | SEMANTIC | Quy định về góp vốn của thành viên được nêu ở đâu? | `168859_D10_011` | khong |
| Q016 | SEMANTIC | Quy định về sửa đổi một số khoản của Điều 14 được nêu ở đâu? | `185630_D11_019` | khong |
| Q021 | MIXED | Theo 44/2011/TT-NHNN, tổ chức của kiểm toán nội bộ được quy  | `27257_D12_021` | co |

## 5. Gioi han cua ket luan

- Bo cau hoi chi 24 cau, sinh tu dinh dang co san cua van ban (so hieu + tieu de Dieu), nen **khong dai dien cho cau hoi tu nhien cua nguoi dung that**.
- Moi cau hoi chi co DUNG MOT gold chunk. Thuc te nhieu Dieu khac cung co the tra loi dung, nen Hit@k o day la **can duoi** cua chat luong that.
- Cau hoi SEMANTIC van tai su dung nguyen van tieu de Dieu, nen con loi the tu vung; muon do dung han phai co cau hoi do nguoi dung viet lai bang ngon ngu cua ho.
- Dense dang chay FALLBACK (TF-IDF+SVD), **khong** phai embedding neural, nen so lieu cot `dense` va `hybrid` chua phan anh dung suc manh semantic.
