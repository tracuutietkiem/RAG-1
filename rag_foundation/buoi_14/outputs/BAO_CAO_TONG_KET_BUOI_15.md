# Báo cáo tổng kết — Buổi 15: RBAC ở mức Dữ liệu và Retrieval Pipeline

Dự án: `buoi_14/` (nâng cấp từ Hybrid Search + Reranking + Mini Knowledge Graph của Buổi 14)
Thời điểm: 17/08/2026

---

## 1. Vai trò (Roles) đã thiết lập

Nguồn chân lý duy nhất: `roles.json` (đọc qua `config.ALL_ROLES` để tránh gõ sai role ở bất kỳ file nào).

| Vai trò | Ý nghĩa |
|---|---|
| `Admin` | Toàn quyền xem mọi tài liệu |
| `HR` | Nhân sự, lương thưởng, bổ nhiệm/miễn nhiệm, quản trị nội bộ |
| `Risk_Manager` | Cấp tín dụng, hạn mức, phân loại nợ, an toàn vốn |
| `Staff` | Nghiệp vụ chung + một phần tài liệu rủi ro tín dụng |
| `Guest` | Chỉ tài liệu quy định chung, không nhạy cảm |

---

## 2. Gắn thẻ bảo mật (Security Tagging)

Script: `scripts/assign_security_tags.py` → `data/processed/chunks_secure.csv`

Phân loại ở mức **từng Điều/khoản** (chunk), không phải cả văn bản — vì một văn bản luật/thông tư thường vừa có Điều nhạy cảm (nhân sự, tín dụng) vừa có Điều quy định chung. Nguyên tắc ưu tiên: **most-restrictive-wins** (kiểm tra từ khóa HR trước Risk_Manager).

| Nhóm | Số chunk | allowed_roles |
|---|---|---|
| HR | 478 | `[Admin, HR]` |
| Risk_Manager | 822 | `[Admin, Risk_Manager, Staff]` |
| Chung (General) | 1.228 | `[Admin, HR, Risk_Manager, Staff, Guest]` |
| **Tổng** | **2.528** | — |

Kiểm tra: 0/2.528 dòng có `allowed_roles` rỗng.

---

## 3. Nạp vào Neo4j (Secure Graph Loading)

Script: `scripts/load_secure_kg.py` → `outputs/rbac_kg_load_report.md`

Đã viết và kiểm thử đầy đủ logic (MERGE theo id có sẵn, không `DETACH DELETE`, gắn `rbac_lab_session="buoi_15"`). **Chưa nạp được vào Neo4j thật** vì môi trường chạy việc này (cloud) không kết nối được tới Neo4j Desktop đang chạy ở `127.0.0.1:7687` trên máy bạn — đây là giới hạn về hạ tầng, không phải lỗi code.

**Cần bạn tự chạy trên máy mình** (nơi Neo4j Desktop đang mở):
```bash
cd buoi_14
python scripts/load_secure_kg.py
```

---

## 4. Secure Retrieval Pipeline

File: `src/secure_retriever.py`

| Tầng | Cơ chế lọc quyền |
|---|---|
| BM25 | Lọc **DataFrame Pandas** theo `allowed_roles ∩ user_roles` **trước** khi build BM25 index |
| Dense | Hậu lọc (post-filter) trên embedding cache có sẵn — bỏ qua tuần tự mọi ứng viên không đủ quyền cho tới khi đủ `top_k` |
| Hybrid (RRF) | Chỉ nhận candidate đã qua lọc từ BM25 + Dense |
| Reranker | Chỉ nhận candidate Hybrid đã lọc, có kiểm tra "defense-in-depth" lại lần nữa ngay trước khi rerank |
| Graph (Neo4j) | `WHERE any(role IN coalesce(d.allowed_roles, v.allowed_roles, []) WHERE role IN $user_roles)` — nếu Điều khoản không có `allowed_roles` riêng thì kế thừa từ Văn bản cha; nếu cả hai đều thiếu → fail-closed (an toàn tối đa) |

CLI demo: `scripts/secure_search_demo.py --query "..." --roles Guest --method hybrid_rerank`
Web app: `streamlit run app_secure.py` (đã kiểm thử khởi động thành công)

---

## 5. Kiểm định bảo mật (Security Audit)

Script: `scripts/security_audit.py` → `outputs/security_audit_report.md`

**5 test case × 4 phương pháp (bm25/dense/hybrid/hybrid_rerank) = 20 lượt kiểm tra rò rỉ — TẤT CẢ PASS.**

| # | Test case | Target chunk | Không được phép | Được phép | Kết quả |
|---|---|---|---|---|---|
| 1 | Bổ nhiệm Trưởng kiểm toán nội bộ | `27257_D14_023` | Guest | HR | ✅ PASS |
| 2 | Miễn nhiệm Chủ tịch HĐQT | `166170_D46_062` | Staff | Admin | ✅ PASS |
| 3 | Nhiệm kỳ Tổng giám đốc | `166170_D22_027` | Risk_Manager | HR | ✅ PASS |
| 4 | Giới hạn cấp tín dụng | `166170_D136K1_214` | Guest | Risk_Manager | ✅ PASS |
| 5 | Quản lý khoản cấp tín dụng có vấn đề | `186888_D33_052` | HR | Staff | ✅ PASS |

**Kết luận: hệ thống đạt chứng nhận an toàn dữ liệu mức cơ bản** — không có trường hợp nào vai trò thiếu quyền nhìn thấy tài liệu nhạy cảm của vai trò khác.

> ⚠️ Lưu ý: báo cáo này chạy bằng backend fallback (LSA + lexical) vì môi trường cloud không tải được model neural/không nối được Neo4j của bạn. Cơ chế lọc quyền không phụ thuộc backend, nhưng để có kết quả cuối cùng bằng đúng model thật, hãy chạy lại `python scripts/security_audit.py` trên máy bạn với `.env` gốc (`sentence_transformers` + `cross_encoder`).

---

## 6. Việc còn lại (cần bạn tự làm trên máy mình)

1. Chạy `python scripts/load_secure_kg.py` để nạp `allowed_roles` vào Neo4j thật.
2. Chạy lại `python scripts/security_audit.py` với model neural thật để xác nhận kết quả cuối.
3. Mở `streamlit run app_secure.py`, thử đóng vai từng role ở sidebar để cảm nhận trực quan cơ chế RBAC.
4. Tự trả lời 3 câu hỏi thảo luận ở mục 4 của `buoi15.md` (câu 1 và 3 đã được cài đặt sẵn trong `src/secure_retriever.py`, bạn có thể đối chiếu code + comment để củng cố câu trả lời).

---

## 7. Danh sách file đã tạo/cập nhật trong `buoi_14/`

```
roles.json                              [NEW]
config.py                               [SỬA — thêm ALL_ROLES, validate_roles()]
requirements.txt                        [SỬA — thêm pandas]
data/processed/chunks_secure.csv        [NEW]
src/secure_retriever.py                 [NEW]
scripts/assign_security_tags.py         [NEW]
scripts/load_secure_kg.py               [NEW]
scripts/secure_search_demo.py           [NEW]
scripts/security_audit.py               [NEW]
app_secure.py                           [NEW]
outputs/security_audit_report.md        [NEW]
outputs/rbac_kg_load_report.md          [NEW]
```

Toàn bộ 17 test gốc của Buổi 14 (`tests/test_retrieval.py`) vẫn PASS sau khi nâng cấp — không phá vỡ pipeline cũ.
