"""app.py — Giao diện Streamlit cho Buổi 6.

Pipeline: Câu hỏi -> Top-k (ChromaDB) -> Gemini -> Câu trả lời.
Chạy: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import rag

st.set_page_config(page_title="Buổi 6 — RAG với AI Agent", layout="wide")
st.title("Buổi 6 — Hỏi đáp trên dữ liệu Buổi 5 (RAG)")

# --- Sidebar: trạng thái hệ thống -------------------------------------------
with st.sidebar:
    st.header("Trạng thái hệ thống")
    try:
        s = rag.status()
        st.write(f"**PostgreSQL:** {'Đang dùng' if s['storage_backend'] == 'postgres' else 'Chưa có — dùng SQLite cục bộ'}")
        st.write(f"**ChromaDB:** {'Server' if s['chroma_mode'] == 'server' else 'Embedded Local'}")
        st.write(f"**Gemini API Key:** {'Có' if s['gemini_key_present'] else 'Thiếu'}")
        st.write(f"**Đã index:** {s['n_chunks']} chunk / {s['n_documents']} tài liệu")
    except Exception as exc:
        st.error(f"Không lấy được trạng thái: {exc}")

    if not rag.has_gemini_key():
        st.warning("Thiếu GEMINI_API_KEY trong .env — chưa thể Index, chỉ có thể tra cứu (nếu đã index trước đó).")

# --- Main area: Index --------------------------------------------------------
st.subheader("1. Index dữ liệu từ Buổi 5")
st.caption(f"Nguồn: `{rag.CHUNKS_DIR}` (chỉ đọc)")

if st.button("Index ngay", type="primary", disabled=not rag.has_gemini_key()):
    with st.spinner("Đang đọc JSON, tạo embedding và lưu vào PostgreSQL/SQLite + ChromaDB..."):
        try:
            result = rag.index()
            st.success(
                f"Đã index {result.get('indexed', 0)} chunk "
                f"(lưu text: {result.get('storage_backend', '?')}, "
                f"vector: {result.get('chroma_mode', '?')})."
            )
        except Exception as exc:
            st.error(f"Lỗi khi index: {exc}")

st.divider()

# --- Main area: Hỏi đáp -------------------------------------------------------
st.subheader("2. Đặt câu hỏi")
question = st.text_input("Câu hỏi của bạn")
k = st.slider("Số chunk liên quan lấy ra (top-k)", min_value=1, max_value=10, value=5)

if st.button("Hỏi") and question.strip():
    with st.spinner("Đang tìm kiếm và tạo câu trả lời..."):
        try:
            result = rag.ask(question, k=k)
        except Exception as exc:
            st.error(f"Lỗi khi hỏi: {exc}")
            result = None

    if result:
        if result.get("warning"):
            st.warning(result["warning"])

        st.markdown("**Top-k kết quả tra cứu:**")
        if not result["top_k"]:
            st.info("Không tìm thấy chunk liên quan (đã index dữ liệu chưa?).")
        for i, c in enumerate(result["top_k"], start=1):
            with st.expander(f"#{i} — {c['chunk_id']} (trang {c['page_start']}–{c['page_end']})"):
                if c.get("structure_path"):
                    st.caption(c["structure_path"])
                st.text(c["text"])

        if result.get("answer"):
            st.markdown("**Answer (Gemini):**")
            st.write(result["answer"])
