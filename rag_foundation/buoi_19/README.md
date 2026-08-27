# Buổi 19 — Local AI System: Docker + Ollama (Qwen3:0.6b) + Streamlit Dashboard

Trạng thái build trong sandbox: xem `outputs/b19_docker_acceptance_report.md` —
**LOCAL AI SYSTEM READY: NO trong môi trường build này**, lý do DUY NHẤT là
Ollama server chưa chạy thật ở đây (không phải lỗi code/packaging — xem mục
"Giới hạn môi trường sandbox" bên dưới và hướng dẫn chạy thật trên máy bạn).

## Cách chạy lại toàn bộ (đúng thứ tự)

```bash
python scripts/setup_check_b19.py        # PROMPT SETUP
python scripts/internal_lookup.py        # UC1 (demo 3 câu hỏi)
python scripts/compliance_gap.py         # UC2 (787 chunk bên ngoài)
python scripts/compliance_checker.py     # UC3 (demo 3 miền: Kho quỹ, CAR, Tín dụng)
python scripts/audit_checklist_gen.py    # UC4 (demo 2 domain: Kho quỹ, Bảo mật CNTT & AI)

docker compose up -d                     # PROMPT 4 (dựng 2 container)
docker exec -it agribank-ollama-server ollama pull qwen3:0.6b   # tải model lần đầu
docker compose ps                        # xác nhận 2 container ONLINE
# mở http://localhost:8501

python scripts/security_tests_b19.py     # PROMPT 5 (6 bài test)
python scripts/verify_b19_docker.py      # PROMPT 6 (nghiệm thu tổng)
```

Mỗi script ghi báo cáo tương ứng vào `outputs/`.

## Cấu trúc project

Không có `data/` riêng — toàn bộ dữ liệu (`agribank_internal_policies.csv`,
`chunks_combined_secure.csv`) được đọc thẳng (read-only) từ `../buoi_17/data/`
qua biến môi trường trong `.env` (`SOURCE_INTERNAL_POLICY_CSV`,
`SOURCE_COMBINED_SECURE_CSV`) — không copy, không tạo bản sao, tránh drift dữ
liệu giữa các buổi (giống nguyên tắc Buổi 18).

```text
buoi_19/
├── .env                          # LLM_PROVIDER=ollama, OLLAMA_BASE_URL, OLLAMA_MODEL, GEMINI fallback
├── .dockerignore                 # loại .env/__pycache__/outputs khỏi Docker image
├── Dockerfile                    # container "agribank-ai-app"
├── docker-compose.yml            # orchestrate "ollama" + "app"
├── requirements.txt
├── app.py                        # Streamlit UI hợp nhất UC1-UC4 + Audit Log
└── scripts/
    ├── ollama_adapter.py         # PROMPT 1 - OllamaClient (REST API thuần)
    ├── llm_provider.py           # Dispatcher dual-provider (ollama/gemini) dùng chung cho UC1-UC4
    ├── internal_lookup.py        # UC1 (dual-provider, port từ buoi_17)
    ├── compliance_gap.py         # UC2 (dual-provider, port từ buoi_17)
    ├── compliance_checker.py     # UC3 (dual-provider, port từ buoi_18)
    ├── audit_checklist_gen.py    # UC4 (dual-provider, port từ buoi_18)
    ├── setup_check_b19.py        # PROMPT SETUP
    ├── security_tests_b19.py     # PROMPT 5
    └── verify_b19_docker.py      # PROMPT 6
```

## Tái sử dụng, không viết lại

- **RBAC + BM25 (`rbac_filter`, `build_external_index`, `tokenize`)**: giữ
  nguyên logic từ `buoi_18/scripts/compliance_checker.py` (bản thân nó tái
  dùng `buoi_14/src/bm25_retriever.tokenize`). `buoi_19/scripts/compliance_checker.py`
  và `audit_checklist_gen.py` là **bản dual-provider song song**, không sửa
  file gốc của buổi 18.
- **`secure_retrieval_adapter.py`, `audit_logger.py`**: import thẳng từ
  `buoi_17/scripts/` (không copy). `audit_logger.LOG_PATH` được đổi lại
  thành `buoi_19/outputs/audit_log.jsonl` sau khi import — logic
  log_event/_redact/read_events giữ nguyên 100%, chỉ đổi đường dẫn ghi (đúng
  nguyên tắc Buổi 18).
- **`DOMAIN_MAP`**: import thẳng từ `buoi_18/scripts/data_catalog_b18.py`
  (không copy lại 10 domain đã xác lập ở Buổi 18).
- **Rule engine ngưỡng số (floor/ceiling %, ceiling tỷ đồng)**: giữ nguyên
  regex từ `compliance_gap.py`/`compliance_checker.py` gốc.
- **buoi_17/buoi_18 GIỮ NGUYÊN, KHÔNG bị sửa** — Buổi 19 chỉ thêm các file
  `scripts/*.py` MỚI trong `buoi_19/scripts/` (bản dual-provider), để không
  phá vỡ các báo cáo nghiệm thu đã chốt của 2 buổi trước.

## Kiến trúc Dual-Provider (`llm_provider.py`)

Thay vì mỗi engine UC1-UC4 tự gọi thẳng `google.genai`, toàn bộ 4 engine giờ
gọi DUY NHẤT `llm_provider.call_llm(prompt)`:

- `LLM_PROVIDER=ollama` (mặc định) → `OllamaClient.generate()` — HTTP REST
  thuần tới `OLLAMA_BASE_URL` (`http://localhost:11434` khi chạy trực tiếp
  bằng Python, `http://ollama:11434` khi chạy trong Docker Compose — tên
  service Docker nội bộ, KHÔNG phải domain công khai).
- `LLM_PROVIDER=gemini` → giữ lại đường gọi Gemini cũ (fallback/tuỳ chọn để
  đối chiếu chất lượng với Buổi 17/18).
- Nếu provider chính thất bại (offline, timeout, model chưa pull) →
  `call_llm()` trả về `None`, các engine tự động fallback về rule-based/
  extractive đã có sẵn từ Buổi 17/18 — **không tự bịa kết quả**, không thay
  đổi nguyên tắc xuyên suốt 3 buổi.
- `_llm_checklist()` (UC4) tiếp tục dùng cơ chế neo **chunk_id** (không neo
  bằng chuỗi citation dài) để chống fail-closed sai — đã kiểm chứng cần
  thiết với model nhỏ (Qwen3:0.6b dễ chép sai chuỗi dài hơn Gemini).

## Kiến trúc Docker (`Dockerfile` + `docker-compose.yml`)

Quyết định thiết kế quan trọng:

1. **Build context chỉ là `buoi_19/`** (không copy chéo code buổi khác vào
   image). Code/dữ liệu tái sử dụng của `buoi_14/17/18` được gắn qua
   **bind mount read-only** trong `docker-compose.yml`
   (`../buoi_14:/buoi_14:ro`, v.v.) — khớp CHÍNH XÁC với cách các script
   Python resolve đường dẫn tương đối (`../buoi_14` tính từ `BASE_DIR=/app`).
   Lý do: (a) KHÔNG bao giờ bake `.env`/API key thật của buổi khác vào Docker
   image (image có thể bị lưu cache/chia sẻ), (b) không nhân bản dữ liệu lớn
   vào image, (c) sửa code buổi 14/17/18 trên máy phản ánh ngay khi container
   restart, đúng tinh thần "tái sử dụng, không sao chép".
2. **`.env` của buoi_19 chỉ được đọc lúc container KHỞI ĐỘNG** qua `env_file`
   trong compose — không nằm trong `.dockerignore`-loại-trừ nghĩa là không
   bị copy vào image layer (xem `.dockerignore`).
3. **`requirements.txt` KHÔNG có `sentence-transformers`/`torch`** (nặng
   ~2GB+, cần internet để tải, đi ngược tinh thần "Local SLM nhẹ, offline
   hoàn toàn"). `buoi_14/src/dense_retriever.py` đã có sẵn cơ chế fallback
   OFFLINE (LSA/TF-IDF + lexical rerank) khi thiếu sentence-transformers —
   đã kiểm chứng hoạt động đúng trong toàn bộ test của Buổi 19 (xem log chạy
   UC1/UC2). Nếu cần dense retrieval thật, thêm 2 dòng này vào
   `requirements.txt` và rebuild trên máy có đủ dung lượng/mạng ổn định.
4. `docker exec -it agribank-ollama-server ollama pull qwen3:0.6b` — lệnh
   PROMPT 4 dùng `ollama run` sẽ tự pull nếu chưa có, nhưng khuyến nghị dùng
   `ollama pull` trước để tách rõ bước tải model khỏi bước chạy thử.

## Giới hạn môi trường sandbox (đã kiểm chứng trực tiếp)

Môi trường build (sandbox cloud) này **có Docker CLI + daemon hoạt động
được** (`docker --version`, `docker compose version`, `dockerd` khởi động
thành công, `docker compose config` chạy đúng) nhưng **mạng ra ngoài bị
chặn ở tầng hạ tầng đối với Docker Hub và ollama.com**:

```
$ docker pull python:3.10-slim
... 403 Forbidden (registry-1.docker.io)
$ docker pull ollama/ollama:latest
... 403 Forbidden (registry-1.docker.io)
$ curl -I https://ollama.com
... 403 Forbidden
```

Vì vậy trong sandbox này KHÔNG thể: `docker compose build` (dừng ở bước tải
base image `python:3.10-slim`), KHÔNG thể tải Ollama binary/model
`qwen3:0.6b` thật. Đây CHÍNH XÁC là hạn chế đã gặp với Gemini API ở Buổi
17/18 (mạng ra ngoài bị chặn ở tầng hạ tầng), không phải lỗi thiết kế của
Buổi 19.

**Đã kiểm chứng những gì CÓ THỂ kiểm chứng được trong sandbox**:
- `docker compose config` — hợp lệ 100% cú pháp, resolve đúng volume/env/network.
- Toàn bộ 4 engine UC1-UC4 chạy đúng ở chế độ fallback an toàn khi Ollama
  offline (không crash, không bịa, giữ `NEEDS_HUMAN_REVIEW`).
- **Test nội bộ bằng mock Ollama server** (`http.server` giả lập đúng schema
  REST `/api/tags` + `/api/generate`, KHÔNG phải một phần sản phẩm giao cho
  học viên, chỉ dùng để kiểm thử logic adapter): xác nhận `OllamaClient`,
  `llm_provider.call_llm()`, và cơ chế fail-closed neo `chunk_id` của UC4 đều
  hoạt động đúng end-to-end khi có phản hồi thật từ một HTTP server tuân thủ
  đúng giao thức Ollama — bao gồm cả tình huống LLM trả về 1 mục hợp lệ + 1
  mục chunk_id bịa, hệ thống loại đúng 1 mục bịa và giữ lại đúng 1 mục thật.
- Dual-provider switch: xác nhận logic định tuyến đúng (đổi `LLM_PROVIDER`
  gọi đúng nhánh `_call_ollama`/`_call_gemini`), độc lập với việc server có
  online hay không.
- Thử `LLM_PROVIDER=gemini` với `GEMINI_API_KEY` thật (đã xác nhận hoạt động
  ở Buổi 17/18) trong chính sandbox này: cũng bị chặn mạng (403 Forbidden)
  giống hệt Ollama — xác nhận đây là giới hạn mạng CHUNG của sandbox, không
  riêng gì Ollama.

**Trên máy học viên** (Docker Desktop + internet bình thường): `docker
compose up -d` sẽ tải được `python:3.10-slim` và `ollama/ollama:latest`,
`ollama pull qwen3:0.6b` sẽ tải được model thật (~400-600MB tuỳ biến thể),
và `python scripts/verify_b19_docker.py` chạy lại sẽ cho
`LOCAL AI SYSTEM READY: YES` với Qwen3:0.6b thật thay vì fallback.

## Vai trò "KiemToanVien" (UI-only)

Giữ nguyên quyết định của Buổi 18: `roles.json` gốc của `buoi_14` không có
"KiemToanVien" — đây là lựa chọn UI-only trong `app.py`, ánh xạ về phạm vi
RBAC = Admin khi lọc dữ liệu, không sửa file cấu hình dùng chung.

## Demo "Ngắt kết nối Internet" (Air-gapped Demo)

Trên máy thật với Ollama chạy trong Docker: rút dây mạng/tắt Wifi, hệ thống
**vẫn hoạt động bình thường** vì Ollama chạy 100% trên container local
(`http://ollama:11434` trong mạng Docker nội bộ `agribank-ai-network`,
không đi qua Internet). Bài test #6 (`security_tests_b19.py`) đã mô phỏng
đúng tình huống này bằng cách chặn hoàn toàn đường gọi cloud (`_call_gemini`
luôn raise lỗi) và xác nhận UC3/UC4 vẫn phản hồi hợp lệ — trên máy thật,
thay vì rơi về fallback, hệ thống sẽ vẫn dùng được Qwen3:0.6b thật (vì
Ollama không cần Internet để chạy, chỉ cần model đã pull sẵn trong volume
`ollama_data`).

## Nhắc lại nguyên tắc của buổi học

100% kết quả xung đột (UC3)/checklist (UC4) từ Qwen3:0.6b (hay Gemini fallback)
đều gắn `review_status = NEEDS_HUMAN_REVIEW` và citation xác thực từ dữ liệu
gốc (không bao giờ dùng nguyên văn chuỗi LLM trả về làm citation cuối cùng —
luôn resolve qua `chunk_id`/citation thật). Kiểm toán viên phải tự đối chiếu
với quy định hiện hành của Agribank và Ngân hàng Nhà nước trước khi ban hành
kết luận.
