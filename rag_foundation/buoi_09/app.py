"""app.py — Streamlit Multi-query & Hierarchy Explorer (Buổi 09).

NGUYÊN TẮC VẬN HÀNH:
  - Mở trang KHÔNG build hierarchy, KHÔNG index semantic, KHÔNG tải reranker,
    KHÔNG gọi Gemini. Mọi thao tác tốn tài nguyên đều nằm sau một nút bấm.
  - Toàn bộ logic biến đổi dữ liệu nằm ở `ui_helpers.py` để test được mà không
    cần trình duyệt.
  - Không hiển thị API key và không dump stack trace ra giao diện.

Chạy: python -m streamlit run rag_foundation/buoi_09/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import advanced_rag as ar  # noqa: E402
import hierarchical_rag as hr  # noqa: E402
import rag  # noqa: E402
import ui_helpers as uh  # noqa: E402

st.set_page_config(page_title="Buổi 09 — Multi-query & Parent–Child", layout="wide")
st.title("RAG Foundation — Buổi 09: Multi-query & Parent–Child Retrieval")
st.caption(
    "Query fan-out → Hybrid per query → Cross-query RRF → Parent expansion → Parent rerank"
)


# ---------------------------------------------------------------------------
# Nạp config (rẻ, không gọi API)
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def _load_configs():
    return ar.load_advanced_config(), hr.load_hierarchy_config()


try:
    CONFIG, HCFG = _load_configs()
except (ar.AdvancedConfigError, hr.HierarchyError, rag.ConfigError) as exc:
    st.error(f"Lỗi cấu hình `.env`: {exc}")
    st.stop()


def _hierarchy_state():
    try:
        return hr.hierarchy_status(HCFG)
    except Exception as exc:  # noqa: BLE001 — chỉ để hiện trạng thái, không dump trace
        return {"state": "missing", "reason": str(exc)[:200]}


def _collection_state():
    try:
        status = ar.get_advanced_status("hierarchical", CONFIG)
        return {"state": "ready" if status.get("collection_exists") else "missing",
                "count": status.get("document_count")}
    except Exception:  # noqa: BLE001
        return {"state": "unknown", "count": None}


def _notice(n: dict):
    fn = {"success": st.success, "warning": st.warning, "error": st.error}.get(n["level"], st.info)
    fn(f"**{n['status']}** — {n['message']}" + (f"\n\n➜ {n['action']}" if n["action"] else ""))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

hstate = _hierarchy_state()
cstate = _collection_state()
snap = uh.sidebar_snapshot(CONFIG, HCFG, hstate, cstate)

with st.sidebar:
    st.header("Cấu hình")

    mode = st.selectbox(
        "Mode", hr.VALID_MODES, index=hr.VALID_MODES.index(hr.DEFAULT_MODE),
        help="single/multi = số query; flat/parent = đơn vị trả về.",
    )

    st.caption("Tham số chỉnh được lúc chạy")
    ov = {
        "MULTI_QUERY_COUNT": st.slider("MULTI_QUERY_COUNT", 1, 5, HCFG.multi_query_count),
        "PER_QUERY_CANDIDATES": st.slider("PER_QUERY_CANDIDATES", 1, 50, HCFG.per_query_candidates),
        "PARENT_CANDIDATES": st.slider("PARENT_CANDIDATES", 1, 50, HCFG.parent_candidates),
        "FINAL_PARENT_TOP_K": st.slider("FINAL_PARENT_TOP_K", 1, 20, HCFG.final_parent_top_k),
        "RERANK_MIN_SCORE": st.slider("RERANK_MIN_SCORE", 0.0, 1.0,
                                      float(CONFIG.rerank_min_score), 0.01),
    }
    for msg in uh.apply_runtime_overrides(CONFIG, HCFG, ov):
        st.warning(msg)

    st.divider()
    st.caption("Môi trường")
    st.write(f"Strategy: `{snap['strategy']}` (cố định ở Buổi 09)")
    st.write("Gemini API key: " + ("✅ có" if snap["gemini_key_present"] else "❌ chưa cấu hình"))
    st.write(f"Embedding: `{snap['embedding_model']}`")
    st.write(f"Generation: `{snap['generation_model']}`")
    st.write(f"Reranker: `{snap['reranker_model']}`")

    st.divider()
    st.caption("Hierarchy store")
    _notice(uh.describe_status(snap["hierarchy_state"]))
    if snap["child_count"] is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Child", snap["child_count"])
        c2.metric("Parent", snap["parent_count"])
        c3.metric("Ambiguous", snap["ambiguous_count"])
    if snap["hierarchy_built_at"]:
        st.caption(f"Build lúc: {snap['hierarchy_built_at']}")

    st.caption("Collection semantic")
    st.write(f"Trạng thái: `{snap['collection_state']}` | tài liệu: {snap['collection_count']}")

    st.divider()
    st.caption("Thao tác tốn tài nguyên (chỉ chạy khi bấm)")
    if st.checkbox("Tôi hiểu và muốn build lại hierarchy",
                   help=uh.COSTLY_ACTIONS["build_hierarchy"]):
        if st.button("Build hierarchy", use_container_width=True):
            with st.spinner("Đang dựng lại store…"):
                try:
                    m = hr.build_hierarchy(HCFG)
                    st.success(f"Xong: {m['counts']['children']} child / "
                               f"{m['counts']['parents']} parent.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Build thất bại: {str(exc)[:300]}")
    if st.checkbox("Tôi hiểu thao tác này GỌI Embedding API",
                   help=uh.COSTLY_ACTIONS["prepare_semantic"]):
        if st.button("Chuẩn bị semantic index", use_container_width=True):
            with st.spinner("Đang embed và ghi Chroma…"):
                try:
                    r = ar.prepare_semantic("hierarchical", CONFIG)
                    st.success(f"Xong: {r}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Index thất bại: {str(exc)[:300]}")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["1 · Hỏi đáp", "2 · Query Fan-out", "3 · Parent–Child Explorer",
     "4 · So sánh 4 mode", "5 · Evaluation"]
)

st.session_state.setdefault("result", None)
st.session_state.setdefault("compare", None)


# --- Tab 1 -----------------------------------------------------------------

with tab1:
    st.subheader("Hỏi đáp Multi-query Parent–Child RAG")
    question = st.text_area("Câu hỏi", key="question", height=100,
                            placeholder="Điều kiện vay vốn và các nhu cầu vốn không được cho vay?")
    st.caption(f"Mode đang chọn: `{mode}` — {uh.COSTLY_ACTIONS['run_query']}")

    if st.button("Chạy pipeline", type="primary", key="btn_query"):
        if not question.strip():
            st.warning("Hãy nhập câu hỏi.")
        else:
            with st.spinner("Đang chạy… lần đầu có thể phải tải cross-encoder (~2,27 GB)."):
                try:
                    st.session_state["result"] = hr.answer_hierarchical(
                        question, CONFIG, HCFG, mode=mode
                    )
                except Exception as exc:  # noqa: BLE001
                    st.session_state["result"] = None
                    st.error(f"Không chạy được: {str(exc)[:400]}")

    result = st.session_state["result"]
    if result is None:
        st.info("Chưa có kết quả. Nhập câu hỏi rồi bấm **Chạy pipeline**. "
                "Trang này không tự chạy khi tải lại.")
    else:
        for n in uh.collect_status_notices(result):
            _notice(n)

        tr = result["trace"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Generation call", tr["generation_api_calls"], help="Trần cho multi mode: 2")
        m2.metric("Embedding call", tr["embedding_api_calls"], help="Đếm riêng, không tính vào trần")
        m3.metric("Evidence accepted", tr["accepted_count"])
        m4.metric("Tổng thời gian", f"{tr['latency_ms']['total']:.0f} ms")

        if result["status"] == "answered":
            st.markdown("#### Câu trả lời")
            st.write(result["answer"])
            st.markdown("#### Trích dẫn")
            for c in uh.format_citations(result):
                with st.container(border=True):
                    st.markdown(f"**[{c['evidence_id']}]** {c['source']} — {c['pages']}")
                    st.caption(c["path"])
                    st.caption(f"parent: `{c['parent_id']}` · anchor child: "
                               f"`{c['anchor_child_id']}` · {c['supporting_child_count']} child hỗ trợ")
                    st.caption(f"Rerank: {c['score_label']}")
                    if c["ambiguous"]:
                        st.warning("Cấp bậc Chương/Điều được suy ra từ heading — cần đối chiếu "
                                   "văn bản gốc.")
        if result["warnings"]:
            with st.expander(f"Cảnh báo ({len(result['warnings'])})"):
                for w in result["warnings"]:
                    st.write(f"- {w}")


# --- Tab 2 -----------------------------------------------------------------

with tab2:
    st.subheader("Một câu hỏi → nhiều query")
    result = st.session_state["result"]
    if result is None:
        st.info("Chạy pipeline ở tab 1 trước.")
    else:
        cards = uh.query_cards(result)
        cols = st.columns(min(len(cards), 4) or 1)
        for i, card in enumerate(cards):
            with cols[i % len(cols)]:
                with st.container(border=True):
                    tag = "🟦 GỐC" if card["is_original"] else "⬜ SINH"
                    st.markdown(f"**{card['query_id']} · {tag}**")
                    st.write(card["text"])
                    st.caption(f"focus: `{card['focus']}`")
                    if card["validation"] == "ok":
                        st.caption(f"✅ {card['result_count']} kết quả · "
                                   f"{(card['latency_ms'] or 0):.0f} ms")
                    elif card["validation"] == "retrieval_failed":
                        st.error(f"Retrieval lỗi: {str(card['error'])[:120]}")
                    else:
                        st.caption("⏸ không chạy")

        st.markdown("#### Ma trận query × child")
        matrix = uh.query_child_matrix(result)
        if not matrix["rows"]:
            st.info("Không có child hit nào.")
        else:
            table = []
            for r in matrix["rows"]:
                row = {
                    "#": r["multi_query_rank"],
                    "MQ-RRF": round(r["multi_query_rrf_score"], 6),
                    "hỗ trợ": r["support_query_count"],
                }
                for qid in matrix["query_ids"]:
                    row[qid] = r["ranks"].get(qid) if r["ranks"].get(qid) is not None else "—"
                row["child_id"] = r["child_id"]
                table.append(row)
            st.dataframe(table, use_container_width=True, hide_index=True)
            st.caption(matrix["legend"])


# --- Tab 3 -----------------------------------------------------------------

with tab3:
    st.subheader("Cây Parent → Child → Query")
    result = st.session_state["result"]
    if result is None:
        st.info("Chạy pipeline ở tab 1 trước.")
    else:
        nodes = uh.parent_tree(result)
        if not nodes:
            st.info("Mode flat không tạo parent. Chọn `single_parent` hoặc `multi_parent` "
                    "ở thanh bên rồi chạy lại.")
        for node in nodes:
            label = node["label"] or "—"
            head = (f"{'✅' if node['accepted'] else '⛔'} [{label}] {node['path'] or node['parent_id']}"
                    f"  ·  {node['rank_movement']}")
            with st.expander(head, expanded=node["accepted"]):
                if node["ambiguous"]:
                    st.warning("Cấp bậc suy ra từ heading — đối chiếu văn bản gốc.")
                for w in node["warnings"]:
                    st.warning(w)
                c1, c2, c3 = st.columns(3)
                c1.metric("RRF score", f"{node['parent_rrf_score']:.6f}")
                c2.metric("Rerank score",
                          "—" if node["parent_rerank_score"] is None
                          else f"{node['parent_rerank_score']:.4f}")
                c3.metric("Độ dài context", f"{node['char_count']} ký tự")
                st.caption(f"{node['source']} · tr.{node['page_start']}–{node['page_end']} · "
                           f"`{node['parent_id']}`")

                st.markdown("**Child hỗ trợ**")
                for ch in node["children"]:
                    marks = []
                    if ch["is_anchor"]:
                        marks.append("⚓ anchor")
                    if ch["is_scoring"]:
                        marks.append("★ tính điểm")
                    ranks = ", ".join(f"{q}:{r}" for q, r in sorted(ch["query_ranks"].items()))
                    st.markdown(
                        f"- `{ch['child_id']}` · MQ#{ch['multi_query_rank']} "
                        + (f"· {' · '.join(marks)}" if marks else "")
                    )
                    st.caption(f"    query ranks: {ranks or '—'}")
                    st.caption(f"    {ch['snippet']}")

                with st.expander("Xem toàn văn parent", expanded=False):
                    st.text(node["text"])


# --- Tab 4 -----------------------------------------------------------------

with tab4:
    st.subheader("So sánh 4 mode (retrieval-only)")
    st.caption(uh.COSTLY_ACTIONS["run_compare"])
    cq = st.text_area("Câu hỏi so sánh", key="compare_question", height=80)

    if st.button("Chạy so sánh", key="btn_compare"):
        if not cq.strip():
            st.warning("Hãy nhập câu hỏi.")
        else:
            with st.spinner("Đang chạy 4 mode…"):
                try:
                    st.session_state["compare"] = hr.compare_hierarchical_modes(cq, CONFIG, HCFG)
                except Exception as exc:  # noqa: BLE001
                    st.session_state["compare"] = None
                    st.error(f"Không chạy được: {str(exc)[:400]}")

    cmp_res = st.session_state["compare"]
    if cmp_res is None:
        st.info("Chưa chạy. Lệnh này KHÔNG sinh câu trả lời nên rẻ hơn tab 1.")
    else:
        rows = uh.mode_comparison_rows(cmp_res)
        st.dataframe(
            [
                {
                    "mode": r["mode"], "status": r["status"], "đơn vị": r["unit"],
                    "kết quả": r["final_count"], "child lấy về": r["retrieved_child_count"],
                    "parent mở rộng": r["expanded_parent_count"],
                    "context (ký tự)": r["context_chars"],
                    "hệ số mở rộng": None if r["expansion_factor"] is None
                    else round(r["expansion_factor"], 2),
                    "nguồn": r["unique_sources"], "điều": r["unique_articles"],
                    "gen call": r["generation_api_calls"],
                    "embed call": r["embedding_api_calls"],
                    "ms": None if r["latency_ms"] is None else round(r["latency_ms"]),
                }
                for r in rows
            ],
            use_container_width=True, hide_index=True,
        )
        st.warning(uh.COMPARISON_DISCLAIMER)
        for r in rows:
            if r["error"]:
                st.error(f"[{r['mode']}] {r['error']}")
        with st.expander("Evidence ID theo từng mode"):
            for r in rows:
                st.markdown(f"**{r['mode']}** ({r['unit']})")
                st.caption(", ".join(r["evidence_ids"]) or "—")


# --- Tab 5 -----------------------------------------------------------------

with tab5:
    st.subheader("Evaluation")
    st.caption("Tab này CHỈ đọc report có sẵn — không tự chạy evaluator.")
    latest = uh.latest_report()
    if latest is None:
        st.info("Chưa có report nào trong thư mục `reports/`. "
                "Chạy `python evaluate.py` ở terminal để tạo.")
    elif "error" in latest:
        st.error(latest["error"])
    else:
        st.caption(f"Report: `{latest['name']}`")
        warn = uh.gold_label_warning(latest["report"])
        if warn:
            st.warning(warn)
        rows = uh.evaluation_rows(latest["report"])
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Report chưa có số liệu theo mode.")
