#!/usr/bin/env python3
"""
BUOI 15 - PROMPT 4: Streamlit App bao mat (RBAC) cho Hybrid Search + Reranking.

    streamlit run app_secure.py

App nay la ban nang cap CO KIEM SOAT QUYEN TRUY CAP cua app.py (Buoi 14). Moi
truy van deu goi src.secure_retriever.secure_search() - KHONG viet lai pipeline
rieng, va KHONG BAO GIO goi thang src.pipeline.retrieve() (ham do khong loc
quyen) o app nay.

Tinh nang chinh:
  - Sidebar: chon (impersonate) mot hoac nhieu vai tro dang thu nghiem.
  - Ket qua hien thi nhan bao mat ro rang "Quyen xem: [...]".
  - Thong bao so luong ket qua bi an do khong du quyen.
  - Graph hints cung duoc loc theo quyen dang chon.
"""

import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from src import secure_retriever  # noqa: E402

st.set_page_config(page_title="RAG Secure Search (RBAC) — Buổi 15", layout="wide")


def _ensure_fresh_modules() -> None:
    import importlib

    for mod, attr in ((secure_retriever, "secure_search"),):
        if not hasattr(mod, attr):
            importlib.reload(mod)


_ensure_fresh_modules()

METHOD_LABELS = {
    "BM25": "bm25",
    "Dense": "dense",
    "Hybrid": "hybrid",
    "Hybrid + Rerank": "hybrid_rerank",
}


@st.cache_resource(show_spinner="Đang nạp corpus bảo mật (chunks_secure.csv)...")
def warmup() -> dict:
    records = secure_retriever.load_secure_records()
    info = {
        "n_chunks": len(records),
        "n_docs": len({r["document_id"] for r in records}),
    }
    try:
        dinfo = __import__("src.dense_retriever", fromlist=["dense_info"])
        from src import pipeline
        info.update(pipeline.dense_info())
    except Exception:  # noqa: BLE001
        pass
    return info


def role_badge(roles: list[str]) -> str:
    return " ".join(f"`{r}`" for r in roles)


def render_result(r: dict, method: str, current_roles: list[str]) -> None:
    head = f"#{r['rank']} · `{r['chunk_id']}` · {r['citation'][:80]}"
    with st.expander(head, expanded=r["rank"] <= 3):
        c = st.columns(4)
        c[0].metric("rank", r["rank"])
        c[1].metric("score", f"{float(r.get('score', r.get('retrieval_score', 0))):.6f}")
        c[2].markdown(f"**document_id**\n\n`{r['document_id']}`")
        c[3].markdown(f"**retrieval_method**\n\n`{r['retrieval_method']}`")

        st.markdown(f"🔒 **Quyền xem:** {role_badge(r.get('allowed_roles', []))}")

        if method in ("hybrid", "hybrid_rerank"):
            b = st.columns(3)
            b[0].markdown(f"**bm25_rank**: `{r.get('bm25_rank') or '—'}`")
            b[1].markdown(f"**dense_rank**: `{r.get('dense_rank') or '—'}`")
            b[2].markdown(f"**rrf_score**: `{r.get('rrf_score', '—')}`")
        if method == "hybrid_rerank":
            b = st.columns(3)
            b[0].markdown(f"**hybrid_rank**: `{r.get('hybrid_rank', '—')}`")
            b[1].markdown(f"**hybrid_score**: `{r.get('hybrid_score', '—')}`")
            b[2].markdown(f"**rerank_score**: `{r.get('rerank_score', '—')}`")

        st.markdown(f"**Citation:** {r['citation']}")
        st.text_area("Nội dung", r["text"], height=180, key=f"txt_{method}_{r['chunk_id']}")


def main() -> None:
    st.title("RAG Secure Search — Buổi 15 (RBAC)")
    st.caption(
        "BM25 + Dense → lọc quyền → Hybrid (RRF) → lọc lại → Reranking → Top-k + Citation. "
        "Mọi bước lọc quyền diễn ra TRƯỚC khi dữ liệu tới Reranker."
    )

    try:
        info = warmup()
    except FileNotFoundError as exc:
        st.error(f"{exc}")
        st.info("Chạy trước: `python scripts/assign_security_tags.py`")
        st.stop()

    # ------------------------------------------------------------ Sidebar
    with st.sidebar:
        st.header("⚙️ Cấu hình tìm kiếm")
        label = st.selectbox("Method", list(METHOD_LABELS.keys()), index=3)
        top_k = st.number_input("Top-k", min_value=1, max_value=20, value=config.FINAL_TOP_K)
        candidate_k = st.number_input("Candidate-k", min_value=5, max_value=100,
                                       value=config.CANDIDATE_K)

        st.divider()
        st.header("🎭 Vai trò của bạn (Your Roles)")
        st.caption("Đóng vai (impersonate) một hoặc nhiều vai trò để kiểm thử RBAC.")
        selected_roles = st.multiselect(
            "Chọn vai trò",
            options=config.ALL_ROLES,
            default=[config.DEFAULT_ROLE] if config.DEFAULT_ROLE in config.ALL_ROLES else [],
            help=f"Danh sách vai trò hợp lệ (roles.json): {config.ALL_ROLES}",
        )
        if not selected_roles:
            st.warning("Chưa chọn vai trò nào — chưa thể tìm kiếm.")

        st.divider()
        st.caption(f"Corpus bảo mật: **{info['n_chunks']}** chunk / **{info['n_docs']}** văn bản")
        if "dense_backend" in info:
            tag = "" if info.get("dense_is_neural") else " (FALLBACK)"
            st.caption(f"Dense backend: `{info.get('dense_backend')}`{tag}")

    # ------------------------------------------------------------ Main search
    with st.form("secure_search"):
        question = st.text_input(
            "Câu hỏi",
            value="Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức?",
            placeholder="Nhập câu hỏi nghiệp vụ hoặc số hiệu văn bản...",
        )
        submitted = st.form_submit_button("🔍 Tìm kiếm", type="primary", use_container_width=True)

    if not submitted:
        st.info("Chọn vai trò ở sidebar, nhập câu hỏi rồi bấm **Tìm kiếm**.")
        return
    if not question.strip():
        st.warning("Chưa nhập câu hỏi.")
        return
    if not selected_roles:
        st.error("Chưa chọn vai trò nào ở sidebar — không thể xác định phạm vi quyền truy cập.")
        return

    method = METHOD_LABELS[label]
    t0 = time.perf_counter()
    with st.spinner(f"Đang chạy `{method}` với vai trò {selected_roles}..."):
        out = secure_retriever.secure_search(
            question, selected_roles, method=method,
            top_k=int(top_k), candidate_k=int(candidate_k),
        )
    elapsed = (time.perf_counter() - t0) * 1000

    st.success(
        f"`{method}` — {len(out['results'])} kết quả trong {elapsed:.0f} ms "
        f"— vai trò đang dùng: {role_badge(out['user_roles'])}"
    )

    # ---- thông báo số kết quả bị lọc do không đủ quyền (Prompt 4, mục 3) ----
    hidden = out.get("n_hidden_chunks", 0)
    total = out.get("n_total_chunks", 0)
    st.info(
        f"🔒 Phạm vi hiện tại: **{out.get('n_visible_chunks', 0)}/{total}** chunk khả kiến — "
        f"đã lọc bỏ **{hidden}** chunk do không đủ quyền truy cập.",
        icon="🔒",
    )

    st.subheader(f"Top-{int(top_k)}")
    if not out["results"]:
        st.warning("Không có kết quả nào trong phạm vi quyền truy cập hiện tại.")
    for r in out["results"]:
        render_result(r, method, selected_roles)

    # ------------------------------------------------ Before / After rerank
    if method == "hybrid_rerank" and out["before_rerank"]:
        st.divider()
        st.subheader("Before / After Rerank")
        before = out["before_rerank"][: int(top_k)]
        after = out["results"]
        rows = []
        for i in range(max(len(before), len(after))):
            b = before[i] if i < len(before) else None
            a = after[i] if i < len(after) else None
            rows.append({
                "#": i + 1,
                "BEFORE (Hybrid/RRF)": b["chunk_id"] if b else "",
                "rrf_score": f"{b['rrf_score']:.6f}" if b else "",
                "→": "→",
                "AFTER (Rerank)": a["chunk_id"] if a else "",
                "rerank_score": f"{a['rerank_score']:.6f}" if a else "",
                "vị trí cũ": a.get("hybrid_rank", "") if a else "",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
        moved = sum(1 for a in after if a.get("hybrid_rank") != a["rank"])
        st.caption(f"Reranking đổi chỗ **{moved}/{len(after)}** kết quả trong top-{int(top_k)}.")
        st.caption(
            "Tất cả candidate ở bảng BEFORE đều đã đi qua bước lọc quyền — "
            "Reranker chưa từng nhìn thấy tài liệu bị cấm."
        )

    # ------------------------------------------------ Graph hints (đã lọc quyền)
    st.divider()
    st.subheader("Graph hints (đã lọc theo quyền)")
    hints = secure_retriever.secure_graph_hints(out["results"], out["user_roles"])
    if hints["available"]:
        st.success(hints["message"], icon="✅")
    else:
        st.warning(
            f"{hints['message']} — vẫn liệt kê `document_id` / `chunk_id` để buổi "
            f"Graph RAG sau dùng tiếp.",
            icon="⚠️",
        )
    for d in hints["documents"]:
        st.markdown(f"**Văn bản `{d['so_ky_hieu']}`** — chunk: "
                    + ", ".join(f"`{c}`" for c in d["chunk_ids"]))
        if d["relations"]:
            st.dataframe(
                [{"Quan hệ": r["type"], "Tới": r["target"], "Độ tin cậy": r["confidence"]}
                 for r in d["relations"]],
                use_container_width=True, hide_index=True,
            )
        elif hints["available"]:
            st.caption("Không có quan hệ trực tiếp nào trong phạm vi quyền hiện tại.")
    st.caption(
        "Citation và Graph hints ở trên chỉ hiển thị quan hệ của các văn bản mà "
        "vai trò đang chọn được phép xem — không lộ sự tồn tại của văn bản bị cấm."
    )


if __name__ == "__main__":
    main()
