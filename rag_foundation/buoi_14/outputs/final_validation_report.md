# Bao cao validation cuoi - Buoi 14

- Working root: `/home/claude/buoi_14`
- Du lieu nguon (chi doc): `/mnt/user-data/uploads/phan_mem_tra_cuVB/RAG/rag_foundation/Buổi 12/ner_kb`

## Backend thuc te

- Dense: `lsa` — **FALLBACK (khong phai neural embedding)**
- Reranker: `fallback_lexical_overlap` — **FALLBACK (khong phai neural cross-encoder)**

## Checklist

| # | Muc kiem tra | Ket qua | Chi tiet |
|---|---|---|---|
| 1 | Corpus da chuan hoa | PASS | 2528 chunk / 30 van ban, chunk_id duy nhat |
| 2 | Du file nop bai | PASS | du 28 file bat buoc |
| 3 | BM25 co ket qua | PASS | 5 ket qua |
| 4 | Dense co ket qua | PASS | 5 ket qua |
| 5 | Hybrid dung CA HAI retriever (bm25_rank + dense_rank) | PASS | bm25_rank=True, dense_rank=True |
| 6 | Fusion khong cong raw score sai cach | PASS | dung RRF tren THU HANG, khong cong thang BM25 score voi cosine |
| 7 | Reranker chi xu ly candidate cua Hybrid | PASS | candidate=15 -> top=5, ket qua nam trong candidate |
| 8 | Co Before/After Rerank | PASS | co ca BEFORE (20) va AFTER (5); thu tu CO doi |
| 9 | Citation khong bi mat | PASS | citation con nguyen o ca 4 method |
| 10 | Co evaluation cho ca 4 cau hinh | PASS | 24 cau hoi x 4 cau hinh = 96 dong |
| 11 | Gold cua bo cau hoi xac minh duoc | PASS | moi gold deu ton tai trong corpus |
| 12 | Mini KG co can cu + khong xoa graph buoi truoc | PASS | moi lenh DETACH DELETE deu bi rang buoc lab_session; gan lab_session='buoi_14'=True |
| 13 | Khong ghi vao du lieu nguon | PASS | moi output nam trong buoi_14/, KB_DIR chi doc |
| 14 | Test tu dong pass | PASS | OK |
| 15 | Streamlit dung dung pipeline | PASS | app.py goi dung src.pipeline.retrieve (khong viet lai pipeline rieng) |

**15/15 muc PASS**

## Ket luan

```
READY FOR DEMO: YES
```

> Luu y trung thuc: pipeline dang chay o che do FALLBACK cho Dense va Reranker. Cau truc pipeline va toan bo kiem tra o tren van dung, nhung so lieu chat luong chua phai cua model neural. Tren may co tai duoc model tu HuggingFace, dat `DENSE_BACKEND=sentence_transformers` va `RERANKER_BACKEND=cross_encoder` trong `.env` roi chay lai `scripts/compare_retrieval.py`.