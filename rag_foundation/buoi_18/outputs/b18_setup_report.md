# Buổi 18 — Setup & Data Check Report (PROMPT SETUP)

## 1. Python / venv

- Python 3.14.3 (trong venv)

## 2. Thư mục dự án

- scripts/: co san
- outputs/: co san
- data/: co san
- config/: co san

## 3. Tái sử dụng buoi_17/ và buoi_14/

- buoi_17/scripts/audit_logger.py: tim thay, se reuse
- buoi_17/scripts/secure_retrieval_adapter.py: tim thay
- buoi_14/src/bm25_retriever.py (tokenize dung chung): tim thay
- buoi_14/roles.json (single source of truth RBAC): tim thay

## 4. `agribank_internal_policies.csv` (14 cột metadata)

- So dong: 24, so cot: 14
- Du 14 cot metadata yeu cau: ['chunk_id', 'document_id', 'text', 'source_file', 'title', 'so_ky_hieu', 'loai_van_ban', 'co_quan_ban_hanh', 'ngay_ban_hanh', 'chapter', 'section', 'article', 'citation', 'allowed_roles']
- So van ban noi bo (document_id duy nhat): 10
- Cot co gia tri rong: khong co

## 5. `chunks_combined_secure.csv`

- Tong so chunk: 811 (noi bo: 24, phap ly ben ngoai: 787)
- Phan bo loai_van_ban: {'Nghị định': 300, 'Thông tư': 257, 'Luật': 184, 'Văn bản hợp nhất': 46, 'Quy định nội bộ': 15, 'Quy chế nội bộ': 9}

## 6. Cấu hình `.env` (GEMINI_API_KEY / LLM_API_KEY)

- GEMINI_API_KEY: da dien (53 ky tu)
- LLM_API_KEY: da dien (53 ky tu)
- LLM_MODEL: gemini-3.6-flash
- => Co API key: UC3/UC4 se dung LLM khi co the ket noi mang tu moi truong chay.

## Kết luận

ENVIRONMENT READY: YES
INTERNAL DATA READY: YES
COMBINED DATA READY: YES
