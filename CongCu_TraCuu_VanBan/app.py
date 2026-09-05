#!/usr/bin/env python3
"""
PROMPT 8 - Demo Streamlit cho Hybrid Search + Reranking.

    streamlit run app.py

App KHONG viet lai pipeline rieng: moi truy van deu goi src.pipeline.retrieve()
- dung ham ma CLI va evaluation dang dung.
"""

import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os  # noqa: E402

# Streamlit Cloud: dua secrets (Settings > Secrets) vao os.environ truoc khi
# import config, de vd. RERANKER_BACKEND=fallback co hieu luc tren cloud
# (RAM mien phi khong du tai Cross-Encoder ~2,27 GB).
try:
        for _k, _v in st.secrets.items():
                    os.environ.setdefault(str(_k), str(_v))
except Exception:  # noqa: BLE001
        pass
import config  # noqa: E402
from src import corpus, graph_hints, pipeline  # noqa: E402

st.set_page_config(page_title="RAG Hybrid Search — Buổi 14", layout="wide")


def _ensure_fresh_modules() -> None:
    """
    Streamlit nap lai app.py khi file doi, NHUNG cac module da import trong
    `src/` van nam trong sys.modules o ban cu. Neu app.py moi goi mot ham chua
    co trong ban cu -> AttributeError.

    Ham nay phat hien lech phien ban va nap lai module tu dia, de nguoi dung
    khong phai tat/mo lai app.
    """
    import importlib

    for mod, attr in ((pipeline, "dense_info"),):
        if not hasattr(mod, attr):
            importlib.reload(mod)


_ensure_fresh_modules()

METHOD_LABELS = {
    "BM25": "bm25",
    "Dense": "dense",
    "Hybrid": "hybrid",
    "Hybrid + Rerank": "hybrid_rerank",
}


@st.cache_resource(show_spinner="Đang nạp corpus và khởi tạo BM25 + Dense...")
def warmup() -> dict:
    """Chi nap corpus + Dense. KHONG nap reranker o day: model cross-encoder
    nang ~2,27 GB, chi tai khi nguoi dung thuc su chon 'Hybrid + Rerank'."""
    n = len(corpus.load_chunks())
    info = pipeline.dense_info()
    info["n_chunks"] = n
    info["n_docs"] = len({r["document_id"] for r in corpus.load_chunks()})
    return info


def backend_banner(info: dict) -> None:
    cols = st.columns(2)
    with cols[1]:
        if "rerank_backend" not in info:
            st.info(
                "Reranker: chưa nạp — sẽ tải khi bạn chọn **Hybrid + Rerank** "
                "(lần đầu tải ~2,27 GB).", icon="ℹ️",
            )
    with cols[0]:
        if info["dense_is_neural"]:
            st.success(f"Dense: `{info['dense_backend']}` (neural)", icon="✅")
        else:
            st.warning(
                f"Dense: `{info['dense_backend']}` — **FALLBACK**, không phải embedding neural.\n\n"
                f"{info['dense_detail']}",
                icon="⚠️",
            )
    if "rerank_backend" not in info:
        return
    with cols[1]:
        if info["rerank_is_neural"]:
            st.success(f"Reranker: `{info['rerank_backend']}` (cross-encoder)", icon="✅")
        else:
            st.warning(
                f"Reranker: `{info['rerank_backend']}` — **FALLBACK**, không phải neural reranker.\n\n"
                f"{info['rerank_detail']}",
                icon="⚠️",
            )


def render_result(r: dict, method: str) -> None:
    head = f"#{r['rank']} · `{r['chunk_id']}` · {r['citation'][:90]}"
    with st.expander(head, expanded=r["rank"] <= 3):
        c = st.columns(4)
        c[0].metric("rank", r["rank"])
        c[1].metric("score", f"{float(r.get('score', r.get('retrieval_score', 0))):.6f}")
        c[2].markdown(f"**document_id**\n\n`{r['document_id']}`")
        c[3].markdown(f"**retrieval_method**\n\n`{r['retrieval_method']}`")

        if method in ("hybrid", "hybrid_rerank"):
            b = st.columns(3)
            b[0].markdown(f"**bm25_rank**: `{r.get('bm25_rank') if r.get('bm25_rank') else '—'}`")
            b[1].markdown(f"**dense_rank**: `{r.get('dense_rank') if r.get('dense_rank') else '—'}`")
            b[2].markdown(f"**rrf_score**: `{r.get('rrf_score', '—')}`")
        if method == "hybrid_rerank":
            b = st.columns(3)
            b[0].markdown(f"**hybrid_rank**: `{r.get('hybrid_rank', '—')}`")
            b[1].markdown(f"**hybrid_score**: `{r.get('hybrid_score', '—')}`")
            b[2].markdown(f"**rerank_score**: `{r.get('rerank_score', '—')}`")

        st.markdown(f"**Citation:** {r['citation']}")
        st.text_area("Nội dung", r["text"], height=200, key=f"txt_{method}_{r['chunk_id']}")


def main() -> None:
    st.title("RAG Hybrid Search — Buổi 14")
    st.caption(
        "BM25 + Dense → Hybrid (RRF) → Reranking → Top-k + Citation. "
        "Knowledge Graph đầy đủ xem trong Neo4j Browser."
    )

    try:
        info = warmup()
    except FileNotFoundError as exc:
        st.error(f"{exc}")
        st.stop()

    st.caption(
        f"Corpus: `data/processed/chunks_normalized.csv` — "
        f"{info['n_chunks']} chunk / {info['n_docs']} văn bản"
    )
    backend_banner(info)
    st.divider()

    with st.form("search"):
        question = st.text_input(
            "Câu hỏi",
            value="Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức?",
            placeholder="Nhập câu hỏi nghiệp vụ hoặc số hiệu văn bản...",
        )
        c1, c2, c3 = st.columns([2, 1, 1])
        label = c1.selectbox("Method", list(METHOD_LABELS.keys()), index=3)
        top_k = c2.number_input("Top-k", min_value=1, max_value=20,
                                value=config.FINAL_TOP_K)
        candidate_k = c3.number_input("Candidate-k", min_value=5, max_value=100,
                                      value=config.CANDIDATE_K)
        submitted = st.form_submit_button("Tìm kiếm", type="primary",
                                          use_container_width=True)

    if not submitted:
        st.info("Nhập câu hỏi rồi bấm **Tìm kiếm**.")
        return
    if not question.strip():
        st.warning("Chưa nhập câu hỏi.")
        return

    method = METHOD_LABELS[label]
    t0 = time.perf_counter()
    with st.spinner(f"Đang chạy `{method}`..."):
        out = pipeline.retrieve(
            question, method=method, top_k=int(top_k), candidate_k=int(candidate_k)
        )
    elapsed = (time.perf_counter() - t0) * 1000

    st.success(f"`{method}` — {len(out['results'])} kết quả trong {elapsed:.0f} ms")

    st.subheader(f"Top-{int(top_k)}")
    if not out["results"]:
        st.warning("Không có kết quả nào.")
    for r in out["results"]:
        render_result(r, method)

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
            rows.append(
                {
                    "#": i + 1,
                    "BEFORE (Hybrid/RRF)": b["chunk_id"] if b else "",
                    "rrf_score": f"{b['rrf_score']:.6f}" if b else "",
                    "→": "→",
                    "AFTER (Rerank)": a["chunk_id"] if a else "",
                    "rerank_score": f"{a['rerank_score']:.6f}" if a else "",
                    "vị trí cũ": a.get("hybrid_rank", "") if a else "",
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        moved = sum(1 for a in after if a.get("hybrid_rank") != a["rank"])
        st.caption(f"Reranking đổi chỗ **{moved}/{len(after)}** kết quả trong top-{int(top_k)}.")

    # ------------------------------------------------ Graph hints
    st.divider()
    st.subheader("Graph hints")
    hints = graph_hints.graph_hints(out["results"])
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
                [{"Quan hệ": r["type"], "Tới": r["target"],
                  "Độ tin cậy": r["confidence"]} for r in d["relations"]],
                use_container_width=True, hide_index=True,
            )
        elif hints["available"]:
            st.caption("Không có quan hệ trực tiếp tới văn bản khác.")
    st.caption(
        "Đồ thị đầy đủ (VanBan → DieuKhoan → DieuKhoan) xem trong Neo4j Browser "
        "bằng `cypher/demo_queries.cypher`."
    )


if __name__ == "__main__":
    main()
