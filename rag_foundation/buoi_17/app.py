"""
BUOI 17 - PROMPT 9: Streamlit UI.

KHONG viet lai logic retrieval/gap o day. Moi thu goi lai:
  - scripts/secure_retrieval_adapter.py (RBAC + Hybrid/Rerank cua buoi_14)
  - scripts/internal_lookup.py          (Use Case 1)
  - scripts/compliance_gap.py           (Use Case 2 - doc lai ket qua CSV
                                          da chay san, khong tinh lai moi lan
                                          bam nut vi corpus 787 dong)
  - scripts/audit_logger.py             (audit trail)

Chay:  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

import secure_retrieval_adapter as adapter  # noqa: E402
import internal_lookup as lookup_mod  # noqa: E402
import audit_logger  # noqa: E402
import config as cfg14  # noqa: E402  (buoi_14/config, cho ALL_ROLES)

st.set_page_config(page_title="Secure RAG & Compliance — Buổi 17", layout="wide")

st.title("SECURE RAG & COMPLIANCE — BUỔI 17")
st.warning(
    "⚠️ Demo đào tạo — kết quả AI cần kiểm toán viên xác minh. "
    "Không dùng làm căn cứ kiểm toán/kết luận tuân thủ cuối cùng."
)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Phiên demo")
    user_id = st.text_input("User ID demo", value="demo01")
    user_role = st.selectbox("User Role", options=cfg14.ALL_ROLES, index=cfg14.ALL_ROLES.index(cfg14.DEFAULT_ROLE))

    st.markdown("---")
    st.subheader("Trạng thái Neo4j")
    try:
        import importlib
        sr = importlib.import_module("src.secure_retriever")
        ok, msg = sr.neo4j_status()
        st.write("🟢 Sẵn sàng" if ok else "🔴 Chưa sẵn sàng")
        st.caption(msg)
    except Exception as exc:  # noqa: BLE001
        st.write("🔴 Lỗi kiểm tra")
        st.caption(str(exc))

tab1, tab2, tab3 = st.tabs(["🔎 TRA CỨU QUY ĐỊNH", "⚖️ COMPLIANCE GAP CHECKER", "🧾 AUDIT"])

# ============================================================== TAB 1
with tab1:
    st.subheader("AI tra cứu quy định nội bộ (có RBAC)")
    question = st.text_area("Câu hỏi", placeholder="Điều kiện cấp tín dụng đối với khách hàng doanh nghiệp là gì?")
    top_k = st.slider("Top-k", min_value=1, max_value=10, value=5)
    if st.button("RUN", key="run_lookup"):
        if not question.strip():
            st.error("Nhập câu hỏi trước khi chạy.")
        else:
            with st.spinner("Đang tra cứu (RBAC → Hybrid → Rerank)..."):
                result = lookup_mod.internal_lookup(question, user_role, top_k=top_k, user_id=user_id)
            if result["status"] == "DENIED":
                st.error(f"DENIED: {result.get('error')}")
            else:
                st.markdown("**Answer / Evidence**")
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

# ============================================================== TAB 2
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
            use_container_width=True, height=400,
        )
        st.markdown("**NHNN | INTERNAL | STATUS**")
        for _, r in view.head(5).iterrows():
            st.write(f"`{r['classification']}` — {str(r['external_citation'])[:70]} ↔ "
                     f"{str(r['internal_citation'])[:70] if pd.notna(r['internal_citation']) and r['internal_citation'] else '(không có)'}")
        st.error("NEEDS_HUMAN_REVIEW — mọi dòng trên đều cần kiểm toán viên xác minh trước khi kết luận.")

# ============================================================== TAB 3
with tab3:
    st.subheader("Audit Trail")
    events = audit_logger.read_events()
    if not events:
        st.info("Chưa có audit event nào. Chạy Tab 1 (Tra cứu) để tạo sự kiện.")
    else:
        visible_events = [
            e for e in events
            if user_role in (e.get("user_role") or []) or user_id == e.get("user_id_demo")
        ]
        st.caption(
            f"Hiển thị {len(visible_events)}/{len(events)} audit event phù hợp với role/user demo hiện tại "
            f"({user_role} / {user_id}). Không hiển thị secret."
        )
        for ev in reversed(visible_events[-50:]):
            with st.expander(f"{ev['timestamp_utc']} — {ev['action']} — {ev['status']} — {ev['request_id'][:8]}"):
                st.json(ev)
