"""app.py — UI Streamlit trực quan hoá PDF -> text (OCR/PyMuPDF) -> chunk.

Chạy:
    streamlit run app.py

Chỉ đọc dữ liệu có sẵn trong output/ (đã được tạo bởi `python src/pipeline.py --write`).
Không gọi lại OCR/LLM, không tạo embedding.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "output" / "raw"
CHUNKS_DIR = BASE_DIR / "output" / "chunks"

STRATEGY_LABELS = {
    "fixed_size": "Fixed-size (cắt cố định + overlap)",
    "semantic": "Semantic (theo ranh giới đoạn văn)",
    "hierarchical": "Hierarchical (Chương/Mục/Điều/Khoản/Điểm)",
}

st.set_page_config(page_title="Buổi 5 — RAG Foundation: OCR & Chunking", layout="wide")
st.title("Buổi 5 — Trực quan hoá OCR & Chunking")
st.caption(
    "PDF → text (PyMuPDF / OCR LlamaParse) → chunk theo 3 chiến lược. "
    "Chỉ đọc dữ liệu đã có trong `output/`, không gọi lại OCR/LLM."
)


@st.cache_data
def load_raw_files() -> dict[str, dict]:
    data = {}
    if RAW_DIR.exists():
        for f in sorted(RAW_DIR.glob("*.json")):
            data[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return data


@st.cache_data
def load_chunks(stem: str, strategy: str) -> list[dict]:
    path = CHUNKS_DIR / f"{stem}_{strategy}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


raw_files = load_raw_files()

if not raw_files:
    st.warning(
        "Chưa có dữ liệu trong `output/raw/`. Hãy chạy trước:\n\n"
        "```\npython src/pipeline.py --write\n```"
    )
    st.stop()

with st.sidebar:
    st.header("Chọn dữ liệu")
    stem = st.selectbox("Tài liệu (PDF)", options=list(raw_files.keys()))
    strategy = st.selectbox(
        "Chiến lược chunking",
        options=list(STRATEGY_LABELS.keys()),
        format_func=lambda k: STRATEGY_LABELS[k],
    )

raw = raw_files[stem]
chunks = load_chunks(stem, strategy)

tab_overview, tab_pages, tab_chunks = st.tabs(
    ["📊 Tổng quan & so sánh", "📄 Text gốc theo trang", "🧩 Xem từng chunk"]
)

# --- Tab 1: Tổng quan & so sánh 3 chiến lược ---------------------------------
with tab_overview:
    col1, col2, col3 = st.columns(3)
    ocr_pages = sum(1 for p in raw["pages"] if p["ocr_used"])
    col1.metric("Tổng số trang", len(raw["pages"]))
    col2.metric("Số trang dùng OCR", ocr_pages)
    col3.metric("OCR fallback toàn file", "Có" if raw.get("ocr_fallback_triggered") else "Không")

    st.subheader("So sánh 3 chiến lược chunking")
    rows = []
    for strat_key, label in STRATEGY_LABELS.items():
        c = load_chunks(stem, strat_key)
        if c:
            lengths = [len(x["text"]) for x in c]
            rows.append(
                {
                    "Chiến lược": label,
                    "Số chunk": len(c),
                    "Độ dài min": min(lengths),
                    "Độ dài max": max(lengths),
                    "Độ dài TB": round(sum(lengths) / len(lengths)),
                }
            )
        else:
            rows.append(
                {"Chiến lược": label, "Số chunk": 0, "Độ dài min": "-", "Độ dài max": "-", "Độ dài TB": "-"}
            )
    st.table(rows)

    if chunks:
        st.subheader(f"Phân bố độ dài chunk — {STRATEGY_LABELS[strategy]}")
        st.bar_chart({"Độ dài (ký tự)": [len(c["text"]) for c in chunks]})

# --- Tab 2: Text gốc theo trang ----------------------------------------------
with tab_pages:
    st.subheader("Text sau khi đọc (PyMuPDF hoặc OCR) — đã chuẩn hoá NFC")
    for p in raw["pages"]:
        badge = "🔎 OCR" if p["ocr_used"] else "📃 PyMuPDF"
        with st.expander(f"Trang {p['page']} — {badge} — {len(p['text'])} ký tự"):
            st.text(p["text"] if p["text"].strip() else "(trang rỗng)")

# --- Tab 3: Xem từng chunk -----------------------------------------------------
with tab_chunks:
    st.subheader(f"Danh sách chunk — {STRATEGY_LABELS[strategy]}")
    if not chunks:
        st.info("Chưa có chunk nào cho chiến lược này (kiểm tra lại output/chunks/).")
    else:
        idx = st.slider("Chọn chunk", 1, len(chunks), 1) - 1
        c = chunks[idx]

        meta_cols = st.columns(4)
        meta_cols[0].metric("chunk_id", c["chunk_id"])
        meta_cols[1].metric("Trang", f"{c['page_start']}–{c['page_end']}")
        meta_cols[2].metric("Độ dài", f"{len(c['text'])} ký tự")
        meta_cols[3].metric(
            "Cấu trúc phát hiện",
            "Có" if c.get("structure_detected") else ("Không" if c.get("structure_detected") is False else "—"),
        )

        if c.get("structure_path"):
            st.markdown(f"**Vị trí cấu trúc:** `{c['structure_path']}`")

        st.text_area("Nội dung chunk", c["text"], height=350)

        st.caption(f"Chunk {idx + 1}/{len(chunks)}")
