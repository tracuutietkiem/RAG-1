# Buổi 18 — AI Compliance Checker (UC3) & AI Audit Checklist Generator (UC4)

Trạng thái: **SYSTEM READY FOR DEMO: YES** (xem `outputs/final_validation_b18_report.md`).

## Cách chạy lại toàn bộ (đúng thứ tự)

```bash
python scripts/setup_check_b18.py        # PROMPT SETUP
python scripts/data_catalog_b18.py       # PROMPT 1
python scripts/compliance_checker.py     # PROMPT 2 (UC3 — demo 3 miền: Kho quỹ, CAR, Tín dụng)
python scripts/audit_checklist_gen.py    # PROMPT 3 (UC4 — demo 2 domain: Kho quỹ, Bảo mật CNTT & AI)
streamlit run app.py                     # PROMPT 4 (UI đầy đủ, quét được TẤT CẢ domain, không chỉ demo)
python scripts/security_tests_b18.py     # PROMPT 5 (7 bài test)
python scripts/final_validation_b18.py   # PROMPT 6 (nghiệm thu tổng)
```

Mỗi script ghi báo cáo tương ứng vào `outputs/`.

## Ghi chú cấu trúc & quyết định thiết kế quan trọng

1. **Không có `data/` riêng cho Buổi 18.** Toàn bộ dữ liệu (`agribank_internal_policies.csv`,
   `chunks_combined_secure.csv`) được **đọc thẳng (read-only) từ `../buoi_17/data/`** qua biến
   môi trường trong `.env` — không copy, không tạo bản sao, tránh drift dữ liệu giữa hai buổi.
   `buoi_18/data/` và `buoi_18/config/` để trống có chủ đích.

2. **Tái sử dụng, không viết lại**:
   - `tokenize()` + `BM25Okapi` — từ `buoi_14/src/bm25_retriever.py`.
   - `roles.json` (single source of truth RBAC) — từ `buoi_14/`.
   - `audit_logger.py` (log_event/_redact/read_events) — **import thẳng** từ
     `buoi_17/scripts/audit_logger.py`, chỉ đổi lại biến module-level `LOG_PATH`
     để ghi vào `buoi_18/outputs/audit_log.jsonl` thay vì `buoi_17/outputs/`
     (vì `audit_logger.py` tính `BASE_DIR` từ `__file__` của chính nó — nếu
     không đổi lại, log của Buổi 18 sẽ lẫn vào log của Buổi 17). Logic ghi/redact
     giữ nguyên 100%, chỉ đổi đường dẫn output.
   - Pattern trích xuất ngưỡng số (floor %, ceiling %, ceiling tỷ đồng) — tái sử
     dụng nguyên văn từ `buoi_17/scripts/compliance_gap.py`.

3. **Domain được suy ra từ chính tiêu đề văn bản thật** (`scripts/data_catalog_b18.py`,
   `DOMAIN_MAP`) — 10 văn bản nội bộ ↔ 10 domain cố định, minh bạch, không phải AI tự đoán.
   Dùng chung cho cả UC3 (tìm văn bản đối chiếu cùng domain) và UC4 (lọc theo Domain).

4. **Vai trò "KiemToanVien" (UI-only)**: `roles.json` gốc của `buoi_14` chỉ có 5 vai trò
   (Admin/HR/Risk_Manager/Staff/Guest), không có "KiemToanVien" như đề bài yêu cầu trong
   sidebar. Vì đây là **file cấu hình dùng chung, single source of truth**, Buổi 18
   **không sửa** `roles.json`. Thay vào đó, "KiemToanVien" chỉ là một lựa chọn ở UI
   (`app.py`), được **ánh xạ về phạm vi RBAC = Admin** khi lọc dữ liệu (kiểm toán viên
   cần quyền đọc rộng để đối chiếu) — quyết định này được ghi rõ trong code và UI, không
   ngầm định.

5. **UC3 — vì sao không tự động gán "XUNG_DOT" từ trùng từ khóa**: giống nguyên tắc
   `compliance_gap.py` của Buổi 17, BM25 trên corpus nhỏ luôn tìm được "ứng viên gần nhất"
   dù chỉ trùng từ khóa hành chính chung. Hệ thống UC3 **chỉ tự động gán `XUNG_DOT`** khi
   trích xuất được **ngưỡng số kiểm chứng được trên cả hai phía** (floor %, ceiling %,
   ceiling tỷ đồng) và ngưỡng nội bộ thực sự lỏng hơn/vượt trần pháp luật; nếu có
   `GEMINI_API_KEY` hợp lệ, các cặp không có ngưỡng số sẽ được LLM đọc **nguyên văn 2 đoạn**
   để gợi ý (`llm_assisted`, vẫn cần `NEEDS_HUMAN_REVIEW`). Không có ngưỡng số VÀ không có
   LLM (hoặc LLM không đủ tự tin) → `CHUA_DU_BANG_CHUNG`, không suy đoán.

   **Khác biệt với ví dụ minh hoạ trong đề bài**: đề bài mô tả demo tìm được xung đột
   HIGH giữa `100/QĐ-NHNO-AT` và `01/2014/TT-NHNN` về "xe bọc thép". Đã kiểm tra trực
   tiếp dữ liệu thật: Thông tư 01/2014/TT-NHNN (Điều 50) chỉ yêu cầu "xe chuyên dùng",
   **không có ngưỡng số cụ thể** (không có "≥3 tỷ" hay hạn mức tỷ đồng) để đối chiếu với
   quy định nội bộ — nên rule-engine trả về `CHUA_DU_BANG_CHUNG` cho cặp này (không phải
   `XUNG_DOT`), đúng nguyên tắc "không tự bịa xung đột". Khi chạy trên máy có
   `GEMINI_API_KEY` hoạt động, bước `llm_assisted` có thể phát hiện thêm khác biệt về
   **quy trình/thẩm quyền** (không phải hạn mức số) mà rule-engine không nhìn thấy được —
   đây là lý do thiết kế có cả 2 lớp (rule + LLM tùy chọn).

   Riêng cặp **CAR** (`250/QĐ-NHNO-QLRR` Điều 5 vs `41/2016/TT-NHNN` Điều 6): rule-engine
   phát hiện đúng Agribank quy định CAR tối thiểu 8.5% ≥ 8% của NHNN → `KHONG_XUNG_DOT`
   (đáp ứng, chặt hơn) — đây là ví dụ rule-based hoạt động chính xác trên số liệu thật.

6. **Môi trường build (sandbox cloud) không gọi được Gemini** (chặn mạng ra ngoài ở tầng
   hạ tầng — giống hệt tình huống đã gặp ở Buổi 17) → mọi lần chạy demo trong sandbox này
   đều rơi về rule-based/extractive, được code bắt lỗi và ghi log cảnh báo rõ ràng, KHÔNG
   crash, KHÔNG bịa. Trên máy của bạn (đã xác nhận `GEMINI_API_KEY` hoạt động với
   `gemini-3.6-flash` từ Buổi 17), UC3/UC4 sẽ tự động dùng LLM thật khi chạy lại các
   script/`streamlit run app.py`.

7. **Hạn chế dữ liệu đã biết (UC4 — domain "Bảo mật CNTT & AI")**: tập 787 chunk pháp lý
   bên ngoài trong bộ dữ liệu mô phỏng **không chứa** một Thông tư/Nghị định nào chuyên về
   an toàn thông tin/an ninh mạng ngân hàng — đã kiểm tra trực tiếp, không có văn bản nào
   khớp. Vì vậy checklist domain này vẫn trích dẫn đúng — không bịa — nhưng ứng viên bên
   ngoài đôi khi chỉ liên quan lỏng lẻo (trùng cụm "hệ thống thông tin"/"cơ sở dữ liệu").
   Không che giấu hạn chế này — nêu rõ để kiểm toán viên biết cần bổ sung thủ công.

8. **Lỗi thật đã phát hiện và sửa trong lúc build**: bài test #6 (Unknown Domain) ban đầu
   FAIL — khi domain không tồn tại, hệ thống UC4 lỡ dùng CHÍNH CHUỖI TÊN DOMAIN làm câu
   truy vấn BM25 dự phòng, vô tình tìm ra vài chunk trùng từ khóa ngẫu nhiên rồi sinh
   checklist từ đó (vi phạm nguyên tắc "không bịa khi không có dữ liệu"). Đã sửa: domain
   không có trong `DOMAIN_MAP` → trả về rỗng ngay, không thử BM25 dự phòng. Xem
   `outputs/security_test_b18_report.md` mục test #6.

## Danh sách output

Xem `outputs/` — mỗi PROMPT có báo cáo `.md` riêng, cộng `compliance_conflicts.csv`,
`audit_checklist_results.csv` và `audit_log.jsonl`.

## Đã xác nhận chạy thật với LLM (trên máy học viên, 24/08/2026)

Chạy trực tiếp trên máy có `GEMINI_API_KEY` hoạt động (`gemini-3.6-flash`), dùng venv của
`buoi_14` (venv riêng của `buoi_17` không còn tồn tại trên máy — có thể đã bị dọn cùng lúc
xử lý thư mục lồng thừa; `buoi_14/.venv` có đủ mọi gói cần thiết nên dùng lại, không tạo
venv mới). Kết quả:

- **UC3**: LLM-assisted phát hiện đúng **2 xung đột thật** mà rule-engine không thấy được
  (không có ngưỡng số để so sánh trực tiếp) — ví dụ nổi bật: `250/QĐ-NHNO-QLRR` Điều 18 quy
  định hệ số rủi ro bất động sản kinh doanh 150–200%, trong khi `41/2016/TT-NHNN` Điều 9 quy
  định 75–120% theo LTV → **Severity: HIGH**. Đây là minh chứng lớp LLM-assisted có giá trị
  thật, không chỉ là fallback.
- **UC4**: lần chạy đầu tiên LLM trả lời nhưng **toàn bộ citation bị fail-closed loại bỏ**
  (không khớp chính xác chuỗi citation dài) → hệ thống tự rơi về extractive (đúng thiết kế
  an toàn, nhưng lãng phí chất lượng LLM). Đã sửa: đổi sang neo bằng `chunk_id` (mã ngắn,
  LLM chép chính xác hơn nhiều so với chuỗi citation dài) thay vì so khớp nguyên văn citation
  — sau khi sửa, cả 13/13 mục checklist đều `llm_assisted`, câu hỏi cụ thể kèm đúng số liệu
  thật (vd "từ 3 tỷ đồng trở lên", "từ 50 triệu đồng trở lên"). Citation cuối cùng LUÔN được
  lấy từ dữ liệu gốc theo `chunk_id` đã xác thực, không bao giờ dùng nguyên văn chuỗi LLM trả
  về — giữ nguyên nguyên tắc fail-closed, chỉ đổi cách neo cho bền hơn.
- Toàn bộ 7 bài Security & Guardrail Test và Final Validation chạy lại sau khi sửa: **PASS/
  SYSTEM READY FOR DEMO: YES**.

## Nhắc lại nguyên tắc của buổi học

AI Compliance Checker (UC3) và AI Audit Checklist Generator (UC4) **không phải kết luận
kiểm toán cuối cùng** — mọi finding/mục checklist đều `NEEDS_HUMAN_REVIEW`. Kiểm toán viên
phải tự đối chiếu với quy định hiện hành của Agribank và Ngân hàng Nhà nước trước khi ban
hành kết luận.
