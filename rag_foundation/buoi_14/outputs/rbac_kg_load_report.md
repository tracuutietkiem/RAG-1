# Bao cao nap thuoc tinh RBAC (allowed_roles) vao Neo4j - Buoi 15

- Nguon: `data/processed/chunks_secure.csv`
- Cap nhat node: `(:VanBan)` va `(:DieuKhoan)` da nap tu Buoi 14
- Thuoc tinh moi: `allowed_roles` (List<String>), `rbac_lab_session = "buoi_15"`, `rbac_tagged_at`

## 1. Mo hinh cap nhat (truoc khi cham Neo4j)

- So node `VanBan` se cap nhat: **30**
- So node `DieuKhoan` se cap nhat: **2528**

## 2. Ket qua nap

```
NOT RUN
```
**Ly do:** Khong ket noi/nap duoc Neo4j: ServiceUnavailable: Couldn't connect to 127.0.0.1:7687 (resolved to ('127.0.0.1:7687',)):
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [WinError 10061] No connection could be made because the target machine actively refused it)

Cach chay lai khi Neo4j (Neo4j Desktop / server cuc bo) da san sang:

```bash
# .env cuc bo (buoi_14/.env) da co NEO4J_URI/USER/PASSWORD/DATABASE tu Buoi 14
pip install neo4j
python scripts/load_secure_kg.py
```

> Luu y: neu ban dang chay Neo4j Desktop TREN CHINH MAY DANG THUC THI SCRIPT NAY, script se ket noi duoc qua `bolt://127.0.0.1:7687`. Neu script duoc chay tu moi truong khac (vi du moi truong dam may/cloud sandbox), `127.0.0.1` se KHONG tro toi Neo4j tren may cua ban - day la ly do pho bien nhat gay NOT RUN.

## 3. An toan du lieu

- Khong chay `MATCH (n) DETACH DELETE n` trong bat ky truong hop nao.
- Chi dung `MERGE` theo `id` co san -> chay lai nhieu lan KHONG tao node trung, chi ghi de thuoc tinh `allowed_roles`.
- Node moi tao (neu Buoi 14 chua nap) duoc danh dau rieng `lab_session = "buoi_15"` de phan biet voi node goc cua Buoi 14.