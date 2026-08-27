"""
BUOI 19 - PROMPT 3/4 (theo cau truc de bai): Streamlit UI hop nhat 4 Use Case
(UC1-UC4) chay tren Local AI Docker (Ollama + Qwen3:0.6b) hoac Gemini cloud
(tuy LLM_PROVIDER trong .env).

KHONG viet lai logic o day - moi thu goi lai scripts/ cua chinh Buoi 19 (da
duoc cap nhat dual-provider o PROMPT 2):
  - scripts/internal_lookup.py        (UC1)
  - scripts/compliance_gap.py         (UC2 - doc ket qua CSV da chay san,
                                        khong tinh lai moi lan bam nut vi
                                        corpus 787 dong, giong buoi_17)
  - scripts/compliance_checker.py     (UC3)
  - scripts/audit_checklist_gen.py    (UC4)
  - scripts/audit_logger.py           (audit trail)
  - scripts/ollama_adapter.py         (hien thi trang thai Ollama server that)

Chay:  streamlit run app.py   (hoac trong Docker: docker compose up -d)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
sys.path.insert(0, str((BASE_DIR / "../buoi_14").resolve()))

import internal_lookup as uc1  # noqa: E402
import compliance_checker as uc3  # noqa: E402
import audit_checklist_gen as uc4  # noqa: E402
import audit_logger  # noqa: E402  (LOG_PATH da duoc doi ve outputs/ cua buoi_19 qua uc3/uc4)
from ollama_adapter import OllamaClient  # noqa: E402
from data_catalog_b18 import DOMAIN_MAP  # noqa: E402
import config as cfg14  # noqa: E402

st.set_page_config(page_title="Agribank Local AI (Ollama + Docker) — Buổi 19", layout="wide")

st.title("AGRIBANK LOCAL AI SYSTEM — BUỔI 19 (OLLAMA + DOCKER)")
st.warning(
    "⚠️ Demo sản phẩm AI Kiểm toán/Tuân thủ — Kết quả gợi ý cần kiểm toán viên xác minh trước khi ban hành. "
    "AI không thay thế quy trình thẩm định/kết luận kiểm toán của con người."
)

# ------------------------------------------------------------------ sidebar
UI_ROLES = list(cfg14.ALL_ROLES) + ["KiemToanVien"]
ROLE_TO_RBAC = {r: r for r in cfg14.ALL_ROLES}
ROLE_TO_RBAC["KiemToanVien"] = "Admin"

with st.sidebar:
    st.header("Phiên demo")
    user_id = st.text_input("User ID demo", value="auditor01")
    user_role_ui = st.selectbox("User Role", options=UI_ROLES, index=UI_ROLES.index("KiemToanVien"))
    effective_role = ROLE_TO_RBAC[user_role_ui]
    if user_role_ui == "KiemToanVien":
        st.caption("ℹ️ KiemToanVien dùng phạm vi RBAC = Admin (đọc rộng để đối chiếu kiểm toán).")

    st.markdown("---")
    st.subheader("🧠 Local AI Provider")
    provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
    st.write(f"**LLM_PROVIDER** = `{provider}`")
    if provider == "ollama":
        client = OllamaClient()
        health = client.check_health()
        if health["online"] and health["model_ready"]:
            st.success(f"🟢 Ollama ONLINE — model `{client.model}` sẵn sàng ({health['base_url']})")
        elif health["online"]:
            st.warning(f"🟡 Ollama ONLINE nhưng model `{client.model}` CHƯA được pull "
                       f"(`docker exec -it agribank-ollama-server ollama pull {client.model}`).")
        else:
            st.error(f"🔴 Ollama OFFLINE ({health['base_url']}) — hệ thống sẽ tự động dùng "
                     "fallback rule-based/extractive, KHÔNG bịa kết quả. Xem README.md để khởi động Ollama.")
        st.caption(health.get("error") or f"Models đã tải: {health.get('models', [])}")
    else:
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        st.write("🟢 GEMINI_API_KEY đã cấu hình" if gemini_key else "🔴 Thiếu GEMINI_API_KEY")

    st.markdown("---")
    st.subheader("Trạng thái dữ liệu")
    internal_csv = BASE_DIR / os.environ.get("SOURCE_INTERNAL_POLICY_CSV", "../buoi_17/data/agribank_internal_policies.csv")
    combined_csv = BASE_DIR / os.environ.get("SOURCE_COMBINED_SECURE_CSV", "../buoi_17/data/chunks_combined_secure.csv")
    st.write("🟢 Internal policies" if internal_csv.exists() else "🔴 Internal policies THIẾU")
    st.write("🟢 Combined secure (external legal)" if combined_csv.exists() else "🔴 Combined secure THIẾU")

    st.markdown("---")
    if st.button("🗑️ Reset Session / Clean Audit Log", key="reset_session"):
        if audit_logger.LOG_PATH.exists():
            audit_logger.LOG_PATH.unlink()
        st.success("Đã xoá audit log của phiên demo buổi 19 (outputs/audit_log.jsonl).")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔎 UC1 - TRA CỨU QUY ĐỊNH", "⚖️ UC2 - COMPLIANCE GAP", "🚨 UC3 - COMPLIANCE CHECKER",
    "📋 UC4 - AUDIT CHECKLIST", "🧾 AUDIT LOG & SYSTEM TRAIL",
])

# ============================================================== TAB 1 - UC1
with tab1:
    st.subheader("AI tra cứu quy định nội bộ (có RBAC)")
    question = st.text_area("Câu hỏi", placeholder="Điều kiện cấp tín dụng đối với khách hàng doanh nghiệp là gì?")
    top_k = st.slider("Top-k", min_value=1, max_value=10, value=5)
    if st.button("🔎 Tra cứu", key="run_uc1"):
        if not question.strip():
            st.error("Nhập câu hỏi trước khi chạy.")
        else:
            with st.spinner(f"Đang tra cứu (RBAC → Hybrid → Rerank → LLM [{provider}])..."):
                result = uc1.internal_lookup(question, effective_role, top_k=top_k, user_id=user_id)
            st.session_state["uc1_result"] = result

    result = st.session_state.get("uc1_result")
    if result is not None:
        if result["status"] == "DENIED":
            st.error(f"DENIED: {result.get('error')}")
        else:
            st.markdown("**Trả lời**")
            st.code(result["answer"], language=None)
            st.markdown("**Citation**")
            for c in result["citations"]:
                st.write(f"- {c}")
            if not result["citations"]:
                st.info("Không có citation — không tìm thấy chunk hợp lệ trong phạm vi quyền.")
            col1, col2, col3 = st.columns(3)
            col1.metric("Access Decision", "GRANTED")
            col2.metric("Chunk hiển thị / bị ẩn", f"{result.get('n_visible_chunks','?')}/{result.get('n_hidden_chunks','?')}")
            col3.metric("Chế độ trả lời", result.get("answer_mode", "N/A"))
            st.caption(f"Request ID: `{result['request_id']}`")

# ============================================================== TAB 2 - UC2
with tab2:
    st.subheader("AI Compliance Gap Checker")
    gap_csv = BASE_DIR / "outputs" / "compliance_gap_results.csv"
    if not gap_csv.exists():
        st.error("Chưa có outputs/compliance_gap_results.csv — chạy `python scripts/compliance_gap.py` trước.")
    else:
        gap_df = pd.read_csv(gap_csv)
        st.caption(
            f"Đã chấm {len(gap_df)} yêu cầu bên ngoài (chạy sẵn qua `compliance_gap.py`, "
            "không tính lại mỗi lần bấm nút vì corpus lớn). Dùng ô tìm kiếm để lọc theo văn bản."
        )
        classification_filter = st.multiselect(
            "Lọc theo phân loại",
            options=["DAP_UNG", "THIEU", "CHENH_LECH", "CHUA_DU_BANG_CHUNG"],
            default=["DAP_UNG", "THIEU", "CHENH_LECH"],
        )
        keyword = st.text_input("Tìm theo số ký hiệu / nội dung (tuỳ chọn)")

        view = gap_df[gap_df["classification"].isin(classification_filter)] if classification_filter else gap_df
        if keyword.strip():
            mask = (
                view["external_citation"].astype(str).str.contains(keyword, case=False, na=False)
                | view["internal_citation"].astype(str).str.contains(keyword, case=False, na=False)
            )
            view = view[mask]

        st.dataframe(
            view[["gap_id", "external_citation", "internal_citation", "classification",
                  "reason", "confidence", "review_status"]],
            use_container_width=True, height=350,
        )
        st.error("NEEDS_HUMAN_REVIEW — mọi dòng trên đều cần kiểm toán viên xác minh trước khi kết luận.")

# ============================================================== TAB 3 - UC3
with tab3:
    st.subheader("So sánh chéo & phát hiện xung đột quy định")
    domains = sorted(set(m["domain"] for m in DOMAIN_MAP.values()))
    scan_mode = st.radio("Phạm vi quét", ["Chọn 1 Domain", "Quét toàn bộ"], horizontal=True)
    if scan_mode == "Chọn 1 Domain":
        domain_pick = st.selectbox("Domain", options=domains)
        doc_ids = [d for d, m in DOMAIN_MAP.items() if m["domain"] == domain_pick]
    else:
        doc_ids = None
    use_llm = st.checkbox(f"Dùng LLM hỗ trợ phân loại ({provider})", value=True)

    if st.button("🔍 Phát hiện xung đột & Mâu thuẫn", key="run_uc3"):
        with st.spinner(f"Đang đối chiếu chéo (RBAC → BM25 → Rule-based/LLM [{provider}])..."):
            result_df = uc3.run_compliance_check(
                internal_document_ids=doc_ids, user_role=effective_role, user_id=user_id, use_llm=use_llm,
            )
        st.session_state["uc3_result"] = result_df

    result_df = st.session_state.get("uc3_result")
    if result_df is not None and len(result_df):
        n_conflict = int((result_df["classification"] == "XUNG_DOT").sum())
        n_ok = int((result_df["classification"] == "KHONG_XUNG_DOT").sum())
        n_unclear = int((result_df["classification"] == "CHUA_DU_BANG_CHUNG").sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Xung đột (XUNG_DOT)", n_conflict)
        c2.metric("Không xung đột", n_ok)
        c3.metric("Chưa đủ bằng chứng", n_unclear)

        conflicts = result_df[result_df["classification"] == "XUNG_DOT"]
        if len(conflicts):
            st.markdown("### 🚨 Các xung đột phát hiện được")
            for _, r in conflicts.iterrows():
                sev_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(r["severity"], "⚪")
                with st.expander(f"{sev_color} [{r['severity']}] {r['conflict_type']} — {r['domain']}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Văn bản A (nội bộ)**")
                        st.caption(r["doc_a_citation"])
                        st.write(r["doc_a_text"])
                    with col_b:
                        st.markdown("**Văn bản B (đối chiếu)**")
                        st.caption(r["doc_b_citation"])
                        st.write(r["doc_b_text"])
                    st.info(r["description"])
                    st.caption(f"Phương pháp: `{r['classification_method']}`")
                    st.error(f"review_status: {r['review_status']} — cần kiểm toán viên xác nhận.")
        else:
            st.info("Không phát hiện xung đột định lượng được (rule-based) trong phạm vi đã quét. "
                     "Xem bảng đầy đủ bên dưới — các trường hợp 'chưa đủ bằng chứng' CẦN kiểm toán viên đọc trực tiếp, "
                     "không có nghĩa là chắc chắn không có mâu thuẫn.")

        with st.expander(f"📄 Toàn bộ {len(result_df)} cặp đã đối chiếu (kể cả không xung đột / chưa đủ bằng chứng)"):
            st.dataframe(
                result_df[["domain", "doc_a_citation", "doc_b_citation", "classification",
                           "conflict_type", "severity", "classification_method", "description", "review_status"]],
                use_container_width=True, height=350,
            )

        csv_bytes = result_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Tải CSV", csv_bytes, file_name="compliance_conflicts_session.csv")

# ============================================================== TAB 4 - UC4
with tab4:
    st.subheader("Tạo bản nháp Checklist kiểm toán")
    domains = sorted(set(m["domain"] for m in DOMAIN_MAP.values()))
    col1, col2 = st.columns(2)
    domain_pick = col1.selectbox("Domain (miền kiểm toán)", options=domains, key="uc4_domain")
    unit_pick = col2.selectbox(
        "Unit (đơn vị được kiểm toán)",
        options=["Chi nhánh loại 1", "Chi nhánh loại 2", "Phòng giao dịch", "Khối CNTT",
                 "Phòng Kế toán", "Phòng Khách hàng Doanh nghiệp", "Phòng Khách hàng Cá nhân"],
        key="uc4_unit",
    )

    if st.button("📝 Tạo bản nháp Checklist kiểm toán", key="run_uc4"):
        with st.spinner(f"Đang truy xuất quy định liên quan và sinh checklist (LLM: {provider})..."):
            items = uc4.generate_checklist(domain_pick, unit_pick, user_role=effective_role, user_id=user_id)
        st.session_state["uc4_items"] = items

    items = st.session_state.get("uc4_items")
    if items is not None:
        if not items:
            st.error("Chưa có dữ liệu quy định cho Domain/Unit này trong phạm vi RBAC hiện tại — "
                      "hệ thống KHÔNG tự bịa checklist khi không có căn cứ.")
        else:
            checklist_df = pd.DataFrame(items)
            method = checklist_df["generation_method"].iloc[0] if len(checklist_df) else "?"
            is_llm = method.startswith("llm_assisted")
            st.caption(f"Đã sinh {len(checklist_df)} mục — phương pháp: `{method}` "
                       f"({'LLM có kiểm tra citation thật (fail-closed)' if is_llm else 'trích xuất trực tiếp từ văn bản, không dùng LLM'})")

            risk_filter = st.multiselect("Lọc mức rủi ro", options=["HIGH", "MEDIUM", "LOW"],
                                          default=["HIGH", "MEDIUM", "LOW"])
            view = checklist_df[checklist_df["risk_level"].isin(risk_filter)]

            for _, r in view.iterrows():
                sev_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(r["risk_level"], "⚪")
                with st.expander(f"{sev_color} {r['item_id']} — {r['audit_question'][:90]}"):
                    st.markdown(f"**Câu hỏi kiểm toán**: {r['audit_question']}")
                    st.markdown(f"**Rủi ro tiềm ẩn**: {r['risk_description']}")
                    st.markdown(f"**Khuyến nghị**: {r['recommendation']}")
                    st.caption(f"Nguồn / Citation: {r['source_citation']}")
                    st.error(f"review_status: {r['review_status']}")

            col_dl1, col_dl2 = st.columns(2)
            col_dl1.download_button("⬇️ Tải CSV", checklist_df.to_csv(index=False).encode("utf-8-sig"),
                                     file_name=f"audit_checklist_{domain_pick}_{unit_pick}.csv")
            col_dl2.download_button("⬇️ Tải JSON", checklist_df.to_json(orient="records", force_ascii=False).encode("utf-8"),
                                     file_name=f"audit_checklist_{domain_pick}_{unit_pick}.json")

# ============================================================== TAB 5 - Audit Log
with tab5:
    st.subheader("Audit Log & System Trail")
    events = audit_logger.read_events()
    if not events:
        st.info("Chưa có audit event nào trong phiên buổi 19. Chạy các tab UC1-UC4 để tạo sự kiện.")
    else:
        actions = sorted(set(e["action"] for e in events))
        roles_seen = sorted(set(r for e in events for r in (e.get("user_role") or [])))
        col1, col2 = st.columns(2)
        action_filter = col1.multiselect("Lọc theo Action", options=actions, default=actions)
        role_filter = col2.multiselect("Lọc theo Role", options=roles_seen, default=roles_seen)

        filtered = [
            e for e in events
            if e["action"] in action_filter and any(r in role_filter for r in (e.get("user_role") or []))
        ]
        st.caption(f"Hiển thị {len(filtered)}/{len(events)} audit event. Không hiển thị secret/API key (đã redact).")
        table_rows = [{
            "timestamp": e["timestamp_utc"], "action": e["action"], "user_id": e["user_id_demo"],
            "role": ", ".join(e.get("user_role") or []), "status": e["status"],
            "request_id": e["request_id"][:8],
        } for e in filtered]
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, height=300)

        for ev in reversed(filtered[-30:]):
            with st.expander(f"{ev['timestamp_utc']} — {ev['action']} — {ev['status']} — {ev['request_id'][:8]}"):
                st.json(ev)
