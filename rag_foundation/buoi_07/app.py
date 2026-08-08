"""app.py — Giao diện Streamlit cho Buổi 07.

Chỉ gọi lại các hàm public trong rag.py (load_config/get_status/index_chunks/ask)
— không viết lại RAG logic ở đây. Chạy: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import rag

st.set_page_config(page_title="Buổi 07 — RAG hoàn thiện", layout="wide")
st.title("Buổi 07 — RAG hoàn thiện với AI Agent")

try:
    config = rag.load_config()
    config_error = None
except rag.ConfigError as exc:
    config = None
    config_error = str(exc)

if config_error:
    st.error(f"Lỗi cấu hình (.env): {config_error}")
    st.stop()

strategy = st.sidebar.selectbox(
    "Strategy", list(rag.VALID_STRATEGIES), index=list(rag.VALID_STRATEGIES).index(rag.DEFAULT_STRATEGY)
)

# --- Sidebar: trạng thái hệ thống -------------------------------------------
with st.sidebar:
    st.header("Trạng thái hệ thống")
    try:
        s = rag.get_status(strategy, config)
        st.write(f"**GEMINI_API_KEY:** {'Có' if s['api_key_present'] else 'Chưa cấu hình'}")
        st.write(f"**Embedding model:** {s['embedding_model']} (dim={s['embedding_dim']})")
        st.write(f"**Collection:** `{s['collection_name']}`")
        st.write(f"**Đã tồn tại:** {'Có' if s['collection_exists'] else 'Chưa'}")
        st.write(f"**Số record đã index:** {s['record_count']}")
        if s["collection_exists"] and s["metadata_ok"] is False:
            st.warning("Metadata collection không khớp cấu hình hiện tại — cần chạy Index với Reset.")
    except Exception as exc:
        st.error(f"Không lấy được trạng thái: {exc}")

    if not config.gemini_api_key:
        st.warning("Thiếu GEMINI_API_KEY trong .env — chưa thể Index hoặc Hỏi đáp.")

# --- 1. Index ----------------------------------------------------------------
st.subheader("1. Index dữ liệu từ Buổi 05")
st.caption(f"Nguồn: `{rag.CHUNKS_DIR}` (chỉ đọc) — strategy hiện tại: `{strategy}`")

reset = st.checkbox("Reset (xoá và tạo lại collection đích trước khi index)")

if st.button("Index ngay", type="primary", disabled=not config.gemini_api_key):
    with st.spinner(f"Đang embed và index strategy '{strategy}'... (gọi Gemini tuần tự từng chunk, có thể mất vài phút)"):
        try:
            result = rag.index_chunks(strategy, config, reset=reset)
            st.success(
                f"Đã index {result['chunks_embedded']} chunk vào collection `{result['collection']}` "
                f"(tổng record hiện có: {result['record_count']})."
            )
        except (rag.DataError, rag.EmbeddingError, rag.ChromaError) as exc:
            st.error(f"Lỗi khi index: {exc}")

st.divider()

# --- 2. Hỏi đáp ----------------------------------------------------------------
st.subheader("2. Đặt câu hỏi")
question = st.text_input("Câu hỏi của bạn")
top_k = st.slider("Số evidence lấy ra (top-k)", min_value=1, max_value=20, value=config.default_top_k)

if st.button("Hỏi") and question.strip():
    with st.spinner("Đang truy vấn và tổng hợp câu trả lời..."):
        result = None
        try:
            result = rag.ask(question, strategy, config, top_k=top_k)
        except (rag.DataError, rag.EmbeddingError, rag.ChromaError) as exc:
            st.error(f"Lỗi khi hỏi: {exc}")

    if result:
        status_label = {
            "answered": "Đã trả lời (có căn cứ + trích dẫn)",
            "insufficient_evidence": "Không đủ căn cứ — không gọi mô hình sinh câu trả lời",
            "retrieval_only": "Chỉ có kết quả tra cứu — sinh câu trả lời thất bại",
        }.get(result["status"], result["status"])
        st.markdown(f"**Trạng thái:** {status_label}")

        for w in result["warnings"]:
            st.warning(w)

        if result["answer"]:
            st.markdown("**Trả lời (Gemini):**")
            st.write(result["answer"])

        if result["citations"]:
            st.markdown("**Citations:**")
            for c in result["citations"]:
                st.write(
                    f"[{c['label']}] {c['source']} (trang {c['page_start']}-{c['page_end']}, "
                    f"chunk_id={c['chunk_id']}, distance={c['distance']:.4f})"
                )

        st.markdown(f"**Evidence (top {len(result['evidence'])}):**")
        if not result["evidence"]:
            st.info("Không tìm thấy evidence nào (đã index dữ liệu cho strategy này chưa?).")
        for e in result["evidence"]:
            tag = "đạt ngưỡng" if e["accepted"] else "không đạt ngưỡng"
            with st.expander(
                f"{e['label']} — distance={e['distance']:.4f} — {tag} — trang {e['page_start']}-{e['page_end']}"
            ):
                st.caption(f"chunk_id: {e['chunk_id']} | source: {e['source']}")
                st.text(e["text"])
