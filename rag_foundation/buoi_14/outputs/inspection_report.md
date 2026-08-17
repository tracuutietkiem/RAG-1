# Bao cao kiem tra truoc khi lam - Buoi 14

- Working root: `/home/claude/buoi_14`
- Thu muc du lieu nguon (chi doc): `/mnt/user-data/uploads/phan_mem_tra_cuVB/RAG/rag_foundation/Buổi 12/ner_kb`

> De bai goc gia dinh du lieu o `../kb+hops/`. Tren may thuc te bo 3 file nay nam o `../Buổi 12/ner_kb/`. Code dung bien `KB_DIR` nen khong phu thuoc ten thu muc; khong file nguon nao bi sua hay di chuyen.

## 1. Cau truc `buoi_14/` hien co

- `config.py`
- `scripts/inspect_project.py`

## 2. Ba file du lieu nguon

### `metadata.csv`

- Duong dan: `/mnt/user-data/uploads/phan_mem_tra_cuVB/RAG/rag_foundation/Buổi 12/ner_kb/metadata.csv`
- So dong: **30**
- Encoding doc duoc: `utf-8-sig`
- Cot: `id, title, so_ky_hieu, ngay_ban_hanh, loai_van_ban, ngay_co_hieu_luc, ngay_het_hieu_luc, nguon_thu_thap, ngay_dang_cong_bao, nganh, linh_vuc, co_quan_ban_hanh, chuc_danh, nguoi_ky, pham_vi, thong_tin_ap_dung, tinh_trang_hieu_luc`
- Khoa `id`: duy nhat
- Gia tri rong theo cot: {'ngay_co_hieu_luc': 2, 'ngay_het_hieu_luc': 28, 'nguon_thu_thap': 10, 'ngay_dang_cong_bao': 22, 'nganh': 5, 'linh_vuc': 3, 'chuc_danh': 1, 'nguoi_ky': 1, 'thong_tin_ap_dung': 30}

### `content.csv`

- Duong dan: `/mnt/user-data/uploads/phan_mem_tra_cuVB/RAG/rag_foundation/Buổi 12/ner_kb/content.csv`
- So dong: **30**
- Encoding doc duoc: `utf-8-sig`
- Cot: `id, content_html`
- Khoa `id`: duy nhat
- Gia tri rong theo cot: khong co

### `relationships.csv`

- Duong dan: `/mnt/user-data/uploads/phan_mem_tra_cuVB/RAG/rag_foundation/Buổi 12/ner_kb/relationships.csv`
- So dong: **226**
- Encoding doc duoc: `utf-8-sig`
- Cot: `source, target, relationship_type, method, confidence, evidence`
- Gia tri rong theo cot: khong co

## 3. Quan he giua ba file

- `metadata.id` ∩ `content.id`: **30** (metadata 30, content 30)
- content thieu metadata: khong co
- metadata thieu content: khong co
- `relationships.source` khop `metadata.so_ky_hieu`: **30/30** -> khoa noi cua graph la `so_ky_hieu`
- `relationships.target` khop `so_ky_hieu`: **14/142** -> phan con lai la thuc the khac (nguoi ky, co quan, linh vuc, doi tuong ap dung)

### `relationship_type` THUC SU co trong du lieu

| relationship_type | So luong | Target la van ban? |
|---|---|---|
| `AP_DUNG_CHO` | 113 | khong |
| `KY_BOI` | 30 | khong |
| `THUOC_LINH_VUC` | 30 | khong |
| `BAN_HANH_BOI` | 30 | khong |
| `THAM_CHIEU` | 15 | co (6/6 target la so_ky_hieu) |
| `SUA_DOI_BO_SUNG` | 7 | co (7/7 target la so_ky_hieu) |
| `THAY_THE_BOI` | 1 | co (1/1 target la so_ky_hieu) |

- `method` (nguon suy ra quan he): {'metadata_original': 92, 'rule': 23, 'claude_llm': 111}

## 4. Truong dung cho Retrieval va Citation

| Muc dich | Truong | Ghi chu |
|---|---|---|
| Text retrieval chinh | `content.content_html` | HTML tho, phai parse ra text va cat theo **Dieu** truoc khi index |
| Khoa noi content-metadata | `id` | 1:1, 30/30 |
| Citation - ten van ban | `metadata.title` | |
| Citation - so hieu | `metadata.so_ky_hieu` | tin hieu manh cho BM25 |
| Citation - loai | `metadata.loai_van_ban` | Luat / Nghi dinh / Thong tu |
| Citation - hieu luc | `metadata.tinh_trang_hieu_luc`, `ngay_co_hieu_luc` | |
| Khoa graph | `metadata.so_ky_hieu` | trung voi `relationships.source` |

> `content.csv` KHONG co san cot `chunk_id`/`text`. Buoc chuan hoa corpus (Prompt 1) phai tu sinh `chunk_id` bang cach parse HTML va cat theo Dieu.

## 5. Ra soat code hien co trong `buoi_14/`

| File | Loai | Mau khop |
|---|---|---|
| `scripts/inspect_project.py` | risk | `os\.remove` |
| `scripts/inspect_project.py` | risk | `shutil\.rmtree` |
| `scripts/inspect_project.py` | risk | `open\([^)]*['\"]w['\"]` |
| `scripts/inspect_project.py` | risk | `DETACH\s+DELETE` |
| `scripts/inspect_project.py` | risk | `\bDROP\b` |

> Cac ket qua `open(...,'w')` chi ghi vao `buoi_14/`, khong ghi vao KB_DIR.

## 6. Moi truong

- Python: `3.11.15`
- Interpreter: `/usr/bin/python3`
- Dang chay trong virtualenv: **KHONG**
- `pandas`: co
- `rank_bm25`: co
- `sentence_transformers`: co
- `torch`: co
- `neo4j`: **chua co**
- `streamlit`: **chua co**
- `bs4`: co

## 7. Ket luan

```
PROJECT PRE-CHECK
Working root: /home/claude/buoi_14
Data: /mnt/user-data/uploads/phan_mem_tra_cuVB/RAG/rag_foundation/Buổi 12/ner_kb (metadata 30 / content 30 / relationships 226)
Existing code: 2 file trong buoi_14/
Environment: Python 3.11.15
Potential risks: khong
Safe to continue: YES
```