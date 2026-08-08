"""app.py — Streamlit Advanced RAG comparison dashboard cho Buổi 08.

Chỉ gọi các hàm public trong `rag.py` và `advanced_rag.py` — KHÔNG viết lại
logic retrieval/RRF/rerank ở đây (xem SPEC_buoi_08.md mục 12).

Điểm khác Buổi 07: không chỉ là form hỏi đáp. Giao diện cho thấy toàn bộ
hành trình của từng chunk qua các tầng BM25 -> semantic -> RRF -> reranker,
kèm bảng so sánh 4 mode và latency từng tầng.

Khi mở app: KHÔNG tự index, KHÔNG tự tải model reranker, KHÔNG gọi Gemini.
Mọi thao tác tốn tài nguyên đều phải do người dùng bấm nút.

Chạy: streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import advanced_rag as ar
import rag

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"

st.set_page_config(page_title="Buổi 08 — Advanced RAG", layout="wide")
st.title("Buổi 08 — Advanced RAG: Hybrid Search và Reranking")


# ---------------------------------------------------------------------------
# Config + cache
# ---------------------------------------------------------------------------

try:
    config = ar.load_advanced_config()
    config_error = None
except ar.AdvancedConfigError as exc:
    config = None
    config_error = str(exc)

if config_error:
    st.error(f"Lỗi cấu hình (.env): {config_error}")
    st.stop()


@st.cache_resource(show_spinner=False)
def _cached_bm25_index(strategy: str):
    """Cache BM25 corpus theo strategy — đổi strategy sẽ tạo cache entry riêng."""
    chunks, _stats = rag.load_chunks(strategy=strategy)
    return ar.build_bm25_index(chunks)


@st.cache_resource(show_spinner=False)
def _cached_reranker(model_name: str, device_setting: str):
    """
    Cache reranker resource một lần. CHỈ được gọi khi người dùng chủ động chạy
    mode hybrid_rerank — không gọi lúc mở app.
    """
    return ar.load_reranker(config)


strategy = st.sidebar.selectbox(
    "Strategy", list(rag.VALID_STRATEGIES),
    index=list(rag.VALID_STRATEGIES).index(rag.DEFAULT_STRATEGY),
)
mode = st.sidebar.selectbox(
    "Retrieval mode", list(ar.VALID_MODES),
    index=list(ar.VALID_MODES).index(ar.DEFAULT_MODE),
)

with st.sidebar:
    st.header("Trạng thái hệ thống")
    try:
        status = ar.get_advanced_status(strategy, config)
    except Exception as exc:
        status = None
        st.error(f"Không đọc được trạng thái: {exc}")

    if status:
        st.caption("Dữ liệu")
        st.write(f"Corpus: **{status['corpus_size']}** chunk")
        st.write(f"BM25 sẵn sàng: **{'Có' if status['bm25_ready'] else 'Chưa'}**")

        st.caption("Semantic")
        st.write(f"API key: **{'Có' if status['api_key_present'] else 'Thiếu'}**")
        st.write(f"Model: `{status['embedding_model']}` (dim={status['embedding_dim']})")
        st.write(f"Collection: `{status['semantic_collection']}`")
        st.write(f"Số record: **{status['record_count']}**")
        if status["collection_exists"] and status["metadata_ok"] is False:
            st.warning("Metadata collection không khớp cấu hình — cần chạy lại prepare-semantic --reset.")

        st.caption("Reranker")
        st.write(f"Model: `{status['reranker_model']}`")
        st.write(f"Device: **{status['reranker_device_setting']}**")
        st.write(f"Cache: **{'Đã có' if status['reranker_cache_exists'] else 'Chưa tải'}**")

        st.caption("Cấu hình retrieval")
        st.write(f"BM25 K: {status['bm25_candidates']} | Semantic K: {status['semantic_candidates']}")
        st.write(f"RRF k={status['rrf_k']} | w_bm25={status['rrf_bm25_weight']} w_sem={status['rrf_semantic_weight']}")
        st.write(f"Rerank K: {status['rerank_candidates']} | Final top-k: {status['final_top_k']}")
        st.write(f"Rerank min score: {status['rerank_min_score']}")
        st.write(f"Semantic max distance: {status['max_distance']}")


def _score_legend():
    st.caption(
        "BM25 score: **cao hơn = tốt hơn**. Cosine distance: **thấp hơn = tốt hơn**. "
        "RRF score và rerank score: **cao hơn = tốt hơn**. "
        "Rerank score là giá trị sigmoid đã chuẩn hoá của model — **không phải xác suất đúng**."
    )


def _guard_prerequisites(needs_semantic: bool, needs_reranker: bool) -> bool:
    """Kiểm tra điều kiện trước khi chạy; trả False nếu thiếu (đã hiển thị hướng dẫn)."""
    ok = True
    if needs_semantic:
        if not status or not status["api_key_present"]:
            st.error("Thiếu GEMINI_API_KEY trong .env — không thể chạy mode cần semantic.")
            ok = False
        elif not status["collection_exists"] or status["record_count"] == 0:
            st.error(
                "Chưa có semantic index. Chạy lệnh sau trong terminal rồi tải lại trang:\n\n"
                f"`advanced_rag.py prepare-semantic --strategy {strategy}`"
            )
            ok = False
    if needs_reranker and status and not status["reranker_cache_exists"]:
        st.warning(
            f"Model reranker `{config.reranker_model}` chưa có trong cache. Lần chạy đầu sẽ tải "
            "model (cần Internet, vài GB đĩa và RAM) và có thể rất chậm trên CPU."
        )
    return ok


tab_answer, tab_compare, tab_trace, tab_eval = st.tabs(
    ["Hỏi đáp Advanced RAG", "So sánh Retrieval", "Pipeline Trace", "Đánh giá"]
)


# ---------------------------------------------------------------------------
# Tab 1 — Hỏi đáp
# ---------------------------------------------------------------------------

with tab_answer:
    st.subheader("Hỏi đáp Advanced RAG")
    st.caption(f"Mode đang chọn: `{mode}` (mặc định `hybrid_rerank`). Đổi ở thanh bên trái.")

    question = st.text_input("Câu hỏi của bạn", key="answer_question")
    run = st.button("Chạy Advanced RAG", type="primary", key="answer_run")

    if run and question.strip():
        needs_semantic = mode in ("semantic", "hybrid", "hybrid_rerank")
        needs_reranker = mode == "hybrid_rerank"
        if _guard_prerequisites(needs_semantic, needs_reranker):
            with st.spinner("Đang chạy retrieval, gate và sinh câu trả lời..."):
                try:
                    result = ar.answer(
                        question, config, strategy, mode=mode,
                        bm25_index=_cached_bm25_index(strategy),
                    )
                    st.session_state["last_answer"] = result
                except (rag.DataError, rag.EmbeddingError, rag.ChromaError) as exc:
                    st.error(f"Lỗi: {exc}")
                except Exception as exc:
                    st.error(f"Không chạy được: {exc}")

    result = st.session_state.get("last_answer")
    if result:
        status_style = {
            "answered": st.success,
            "insufficient_evidence": st.warning,
            "retrieval_only": st.warning,
            "reranker_unavailable": st.error,
        }.get(result["status"], st.info)
        status_style(f"Trạng thái: **{result['status']}** — {ar._STATUS_LABEL.get(result['status'], '')}")

        if result["status"] == "reranker_unavailable":
            st.info(
                "Chưa rerank được nên **không hiển thị kết quả RRF như thể đã rerank**. "
                "Hãy tải model bằng lệnh `advanced_rag.py rerank --strategy "
                f"{strategy} --question \"...\"` trong terminal, rồi chạy lại."
            )

        for w in result["warnings"]:
            st.warning(w)

        if result["answer"]:
            st.markdown("**Trả lời:**")
            st.write(result["answer"])

        if result["citations"]:
            st.markdown("**Citations** (map từ metadata thật bằng code, không tin chữ model tự viết):")
            for c in result["citations"]:
                st.write(f"`[{c['label']}]` {c['source']} — trang {c['page_start']}-{c['page_end']} "
                         f"(`{c['chunk_id']}`)")

        st.markdown(f"**Evidence ({len(result['evidence'])}):**")
        _score_legend()
        for e in result["evidence"]:
            badge = f"{e['label']} · ĐẠT" if e["accepted"] else "BỊ LOẠI"
            header = f"{badge} — {e['chunk_id']} (trang {e['page_start']}-{e['page_end']})"
            with st.expander(header, expanded=e["accepted"]):
                cols = st.columns(4)
                cols[0].metric("BM25", f"#{e['bm25_rank']}" if e["bm25_rank"] else "—",
                               f"{e['bm25_score']:.2f}" if e["bm25_score"] is not None else None)
                cols[1].metric("Semantic", f"#{e['semantic_rank']}" if e["semantic_rank"] else "—",
                               f"d={e['semantic_distance']:.4f}" if e["semantic_distance"] is not None else None)
                cols[2].metric("RRF", f"#{e['fused_rank']}" if e["fused_rank"] else "—",
                               f"{e['rrf_score']:.6f}" if e["rrf_score"] is not None else None)
                cols[3].metric("Rerank", f"#{e['rerank_rank']}" if e["rerank_rank"] else "—",
                               f"{e['rerank_score']:.4f}" if e["rerank_score"] is not None else None)
                if e["rank_change"] is not None:
                    st.caption(f"Rank change so với RRF: **{e['rank_change']:+d}** "
                               f"(dương = reranker đẩy lên)")
                if e["matched_by"]:
                    st.caption(f"Tìm thấy bởi: {', '.join(e['matched_by'])}")
                st.text(e["text"])


# ---------------------------------------------------------------------------
# Tab 2 — So sánh retrieval
# ---------------------------------------------------------------------------

with tab_compare:
    st.subheader("So sánh Retrieval: BM25 / Semantic / Hybrid RRF / Hybrid + Rerank")
    st.caption("Tab này **không gọi generation** — chỉ so sánh retrieval và rerank.")

    cmp_question = st.text_input("Câu hỏi để so sánh", key="compare_question")
    cmp_run = st.button("So sánh 4 mode", type="primary", key="compare_run")

    if cmp_run and cmp_question.strip():
        if _guard_prerequisites(needs_semantic=True, needs_reranker=True):
            with st.spinner("Đang chạy 4 mode retrieval..."):
                try:
                    st.session_state["last_compare"] = ar.compare_modes(cmp_question, config, strategy)
                except (rag.DataError, rag.EmbeddingError, rag.ChromaError) as exc:
                    st.error(f"Lỗi: {exc}")
                except Exception as exc:
                    st.error(f"Không chạy được: {exc}")

    cmp = st.session_state.get("last_compare")
    if cmp:
        if cmp["errors"]:
            for m, err in cmp["errors"].items():
                st.error(f"Mode `{m}` không chạy được: {err}")

        ok_modes = [m for m in cmp["modes"] if m in cmp["per_mode"]]

        st.markdown("**Latency từng mode (ms):**")
        lat_cols = st.columns(max(len(ok_modes), 1))
        for col, m in zip(lat_cols, ok_modes):
            col.metric(m, f"{cmp['per_mode'][m]['latency_ms']['total']:.0f} ms")

        st.markdown("**Bảng hành trình của từng chunk:**")
        _score_legend()
        table = []
        for row in cmp["rows"]:
            entry = {
                "chunk_id": row["chunk_id"],
                "bm25_rank": row["bm25_rank"],
                "semantic_rank": row["semantic_rank"],
                "fused_rank": row["fused_rank"],
                "rerank_rank": row["rerank_rank"],
                "rank_change": row["rank_change"],
                "final modes": ", ".join(row["final_modes"]),
            }
            table.append(entry)
        st.dataframe(table, width="stretch")
        st.caption("Ô trống = chunk không xuất hiện ở tầng đó (KHÔNG phải điểm bằng 0).")

        st.markdown("**Top-k theo từng mode (xem chunk nào được thêm / mất / đổi hạng):**")
        panels = st.columns(max(len(ok_modes), 1))
        for col, m in zip(panels, ok_modes):
            with col:
                st.markdown(f"**{m}**")
                for i, c in enumerate(cmp["per_mode"][m]["candidates"], start=1):
                    cid = c["chunk_id"]
                    short = cid if len(cid) <= 28 else "…" + cid[-25:]
                    st.write(f"{i}. `{short}`")


# ---------------------------------------------------------------------------
# Tab 3 — Pipeline trace
# ---------------------------------------------------------------------------

with tab_trace:
    st.subheader("Pipeline Trace")
    st.caption("Số liệu của lần chạy gần nhất ở tab **Hỏi đáp Advanced RAG**.")

    result = st.session_state.get("last_answer")
    if not result:
        st.info("Chưa có dữ liệu. Hãy chạy một câu hỏi ở tab đầu tiên.")
    else:
        trace = result["trace"]
        st.markdown("**BM25 candidates → Semantic candidates → Union/Overlap → Reranked → Accepted**")
        cols = st.columns(5)
        cols[0].metric("BM25 candidates", trace["bm25_candidates"])
        cols[1].metric("Semantic candidates", trace["semantic_candidates"])
        cols[2].metric("Union / Overlap", f"{trace['union']} / {trace['overlap']}")
        cols[3].metric("Reranked", trace["reranked"])
        cols[4].metric("Accepted", trace["accepted"])

        st.markdown("**Latency từng tầng (ms):**")
        lat = trace["latency_ms"]
        lat_cols = st.columns(6)
        for col, key in zip(lat_cols, ("bm25", "semantic", "fusion", "rerank", "generation", "total")):
            col.metric(key, f"{lat[key]:.0f}")
        st.caption(
            "Latency chỉ để quan sát tương đối, không phải benchmark khoa học — "
            "máy đang chạy việc khác sẽ ảnh hưởng số đo."
        )

        st.markdown(f"**Gọi Gemini generation:** {'Có' if trace['generation_called'] else 'Không'}")
        st.markdown("**Chiều tốt của từng loại score:**")
        _score_legend()


# ---------------------------------------------------------------------------
# Tab 4 — Đánh giá
# ---------------------------------------------------------------------------

with tab_eval:
    st.subheader("Đánh giá retrieval (Recall@K, MRR@K, nDCG@K)")
    st.caption(
        "Tab này CHỈ ĐỌC report JSON có sẵn trong `reports/`. Không tự chạy đánh giá hàng loạt "
        "khi mở trang (tránh gọi API ngoài ý muốn). Tạo report bằng `evaluate.py`."
    )

    reports = sorted(REPORTS_DIR.glob("*.json"), reverse=True) if REPORTS_DIR.exists() else []
    if not reports:
        st.info(
            "Chưa có report nào. Chạy lệnh sau trong terminal để tạo:\n\n"
            f"`evaluate.py --strategy {strategy} --k 5`"
        )
    else:
        chosen = st.selectbox("Chọn report", reports, format_func=lambda p: p.name)
        try:
            report = json.loads(chosen.read_text(encoding="utf-8"))
        except Exception as exc:
            report = None
            st.error(f"Không đọc được report: {exc}")

        if report:
            st.caption(
                f"Tạo lúc: {report.get('timestamp', '?')} | strategy: {report.get('strategy', '?')} | "
                f"k={report.get('k', '?')}"
            )
            if report.get("needs_human_review"):
                st.warning(
                    "Gold labels trong bộ đánh giá này vẫn còn `needs_human_review=true` — "
                    "**chưa được chuyên gia pháp lý duyệt**. Không dùng kết quả này để tuyên bố "
                    "mode nào chiến thắng chính thức."
                )
            metrics = report.get("metrics_by_mode")
            if not metrics:
                st.error("Report không có phần `metrics_by_mode` hợp lệ — không kết luận được.")
            else:
                st.dataframe(
                    [{"mode": m, **vals} for m, vals in metrics.items()],
                    width="stretch",
                )
            if report.get("failures"):
                st.error(f"Có {len(report['failures'])} query lỗi khi đánh giá:")
                st.json(report["failures"])
