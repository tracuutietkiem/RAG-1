# Bao cao xay Mini Knowledge Graph - Buoi 14

- Nguon (chi doc): `D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\Buổi 12\ner_kb`
- Corpus: `data/processed/chunks_normalized.csv`
- Nhan phan biet buoi hoc: `lab_session = "buoi_14"`

## 1. relationship_type CO THAT trong `relationships.csv`

| relationship_type | So dong | Xu ly |
|---|---|---|
| `AP_DUNG_CHO` | 113 | target la thuc the `DoiTuongApDung`, KHONG phai van ban -> chi nap khi chay `--with-entities` |
| `KY_BOI` | 30 | target la thuc the `NguoiKy`, KHONG phai van ban -> chi nap khi chay `--with-entities` |
| `THUOC_LINH_VUC` | 30 | target la thuc the `LinhVuc`, KHONG phai van ban -> chi nap khi chay `--with-entities` |
| `BAN_HANH_BOI` | 30 | target la thuc the `CoQuan`, KHONG phai van ban -> chi nap khi chay `--with-entities` |
| `THAM_CHIEU` | 15 | **NAP** - target la so_ky_hieu -> (:VanBan)-[:THAM_CHIEU]->(:VanBan) |
| `SUA_DOI_BO_SUNG` | 7 | **NAP** - target la so_ky_hieu -> (:VanBan)-[:SUA_DOI_BO_SUNG]->(:VanBan) |
| `THAY_THE_BOI` | 1 | **NAP** - target la so_ky_hieu -> (:VanBan)-[:THAY_THE_BOI]->(:VanBan) |

> Khong tao them bat ky relation type nao ngoai danh sach tren. `CONTAINS` va `NEXT` khong den tu suy doan ma den tu **cau truc that** cua van ban: `CONTAINS` = chunk thuoc van ban nao, `NEXT` = thu tu Dieu/khoan trong cung mot van ban.

## 2. Mo hinh graph da dung (truoc khi nap)

- Node `VanBan` (trong corpus): **30**
- Node `VanBan` (duoc tham chieu nhung ngoai corpus, `in_corpus=false`): **0**
- Node `DieuKhoan`: **2528**
- Quan he `CONTAINS`: **2528**
- Quan he `NEXT`: **2498**
- Quan he van ban - van ban: **23** ({'THAM_CHIEU': 15, 'SUA_DOI_BO_SUNG': 7, 'THAY_THE_BOI': 1})
- Bo qua co chu dich: {'KY_BOI': 30, 'THUOC_LINH_VUC': 30, 'AP_DUNG_CHO': 113, 'BAN_HANH_BOI': 30}

## 3. Ket qua nap vao Neo4j

```
RUN OK
```
### Da ghi (MERGE, chay lai khong tao duplicate)

| Doi tuong | So luong |
|---|---|
| VanBan | 30 |
| DieuKhoan | 2528 |
| CONTAINS | 2528 |
| NEXT | 2498 |
| SUA_DOI_BO_SUNG | 7 |
| THAM_CHIEU | 15 |
| THAY_THE_BOI | 1 |

### Dem lai tu database (chi `lab_session = buoi_14`)

| Label | So node |
|---|---|
| DieuKhoan | 2528 |
| VanBan | 30 |

| Quan he | So luong |
|---|---|
| CONTAINS | 2528 |
| NEXT | 2498 |
| SUA_DOI_BO_SUNG | 7 |
| THAM_CHIEU | 15 |
| THAY_THE_BOI | 1 |

### Kiem tra chat luong

- Node khong co lien ket nao (orphan): khong co
- Van ban khong co dieu khoan nao: khong co

## 4. An toan du lieu

- Khong chay `MATCH (n) DETACH DELETE n` trong bat ky truong hop nao.
- Chi dung `MERGE` theo `id` -> chay lai nhieu lan khong tao ban ghi trung.
- Toan bo node/quan he cua bai nay mang `lab_session = "buoi_14"`, nen du lieu cac buoi truoc trong cung database khong bi dung toi.
- Muon xoa rieng du lieu Buoi 14: `python scripts/load_mini_kg.py --clean --yes`.