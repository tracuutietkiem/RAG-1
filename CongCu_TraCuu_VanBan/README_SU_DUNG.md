# Tro ly Tra cuu Van ban (RAG) - Huong dan su dung

Cong cu nay dong goi tu bai Buoi 14 (Hybrid Search + Reranking + Mini Knowledge Graph), tach rieng khoi thu muc bai hoc de dung hang ngay.

## Cai dat loi tat (chi lam 1 lan)

1. Vao thu muc nay, bam dup file **`Tao_Loi_Tat_Desktop.vbs`**.
2. Mot hop thoai xac nhan hien ra - bam OK.
3. Ngoai man hinh Desktop se xuat hien icon **"Tra cuu Van ban (RAG)"**.

## Dung hang ngay

- Bam dup icon **"Tra cuu Van ban (RAG)"** tren Desktop.
- Ung dung chay AN NEN (khong hien cua so den) - sau khoang 5-15 giay, trinh duyet tu mo trang `http://localhost:8501`.
- Lan chay dau tien co the cham hon (tu cai thu vien can thiet) - theo doi tien trinh trong `logs\install.log` neu muon.
- Neu trinh duyet khong tu mo, tu vao `http://localhost:8501`.

## Dung ung dung

- Bam dup file **`stop_app.bat`** trong thu muc nay (chi dung dung tien trinh dang chay o cong 8501, khong anh huong ung dung Python khac).
- Hoac mo Task Manager, tim tien trinh `python.exe`/`streamlit` va ket thuc thu cong.

## Ve muc "Graph hints" (do thi quan he van ban)

Muc nay can **Neo4j Desktop dang chay** (instance `rag2026` o trang thai Running). Neu Neo4j chua mo, phan tim kiem chinh (BM25/Dense/Hybrid/Rerank) van hoat dong binh thuong - chi rieng "Graph hints" se hien canh bao vang.

## Luu y an toan du lieu

- File `.env.txt` trong thu muc nay chua thong tin ket noi Neo4j (da dien san) - KHONG chia se file nay cho nguoi khac, khong dua len mang/git.
- Day la cong cu HO TRO TRA CUU NHANH, khong thay the viec doi chieu van ban goc chinh thuc truoc khi ra quyet dinh nghiep vu.
- Khong dua du lieu khach hang hoac so lieu noi bo chua cong bo vao kho van ban cua cong cu nay.

## Cap nhat kho van ban sau nay

Muon nap them van ban moi, can chay lai `scripts\prepare_corpus.py` (xem `README_ky_thuat.md` de biet chi tiet ky thuat - luu y duong dan `KB_DIR` co the can chinh lai vi thu muc nay nam o vi tri khac thu muc bai hoc goc).
