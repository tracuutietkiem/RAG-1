"""ui_helpers.py — Logic thuần Python cho giao diện Buổi 09.

Tách khỏi `app.py` để test được mà KHÔNG cần trình duyệt, KHÔNG gọi API, KHÔNG
tải model. Mọi hàm ở đây chỉ biến đổi dict/list đã có sẵn thành dữ liệu bảng.

Nguyên tắc: file này KHÔNG được phụ thuộc streamlit, không đọc `.env`, không
chạm mạng. (Có test grep chính file này nên tránh viết nguyên cụm lệnh import.)
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"

# ---------------------------------------------------------------------------
# Bảng trạng thái -> cách xử lý cho người dùng
# ---------------------------------------------------------------------------

# Mỗi status kèm mức độ và HƯỚNG XỬ LÝ cụ thể. Không bao giờ dump stack trace
# hay API key ra giao diện.
STATUS_UX = {
    "answered": (
        "success",
        "Đã sinh câu trả lời từ evidence được chấp nhận.",
        "Đối chiếu lại từng trích dẫn với văn bản gốc trước khi sử dụng.",
    ),
    "hierarchy_not_ready": (
        "error",
        "Hierarchy store chưa sẵn sàng hoặc đã cũ so với dữ liệu chunk.",
        "Bấm nút 'Build hierarchy' ở thanh bên, hoặc chạy lệnh build-hierarchy.",
    ),
    "collection_not_ready": (
        "error",
        "Chưa có collection semantic cho chiến lược hierarchical.",
        "Bấm nút 'Chuẩn bị semantic index' ở thanh bên (thao tác này gọi Embedding API).",
    ),
    "query_generation_unavailable": (
        "warning",
        "Không sinh được query biến thể.",
        "Pipeline vẫn chạy với câu hỏi gốc. Kiểm tra GEMINI_API_KEY và hạn mức, "
        "hoặc dùng mode single_* cho lượt này.",
    ),
    "multi_query_partial": (
        "warning",
        "Một số query biến thể chạy retrieval thất bại.",
        "Kết quả vẫn dùng được nhưng độ phủ thấp hơn thiết kế — xem danh sách "
        "query lỗi ở tab Query Fan-out.",
    ),
    "reranker_unavailable": (
        "error",
        "Cross-encoder không dùng được.",
        "Kết quả CHƯA rerank nên không được hiển thị. Kiểm tra đã cài transformers/torch "
        "và model đã tải xong chưa.",
    ),
    "insufficient_evidence": (
        "warning",
        "Không có evidence nào đạt ngưỡng tin cậy — hệ thống KHÔNG gọi mô hình sinh câu trả lời.",
        "Thử diễn đạt lại câu hỏi, tăng PARENT_CANDIDATES, hoặc hạ RERANK_MIN_SCORE "
        "nếu chấp nhận rủi ro cao hơn.",
    ),
    "retrieval_only": (
        "warning",
        "Lấy được evidence nhưng không sinh được câu trả lời.",
        "Đọc trực tiếp phần evidence bên dưới. Kiểm tra hạn mức Gemini rồi thử lại.",
    ),
    "generation_error": (
        "error",
        "Gọi mô hình sinh câu trả lời thất bại.",
        "Kiểm tra GEMINI_API_KEY, kết nối mạng và hạn mức rồi thử lại.",
    ),
    "ready": ("success", "Sẵn sàng.", ""),
    "stale": (
        "warning",
        "Store đã cũ so với dữ liệu chunk hoặc cấu hình hiện tại.",
        "Build lại hierarchy để đồng bộ.",
    ),
    "missing": (
        "error",
        "Chưa có store.",
        "Bấm 'Build hierarchy' để tạo lần đầu.",
    ),
}


def describe_status(status: str) -> dict:
    """Trả (level, message, action) cho một status. Status lạ không làm vỡ UI."""
    level, message, action = STATUS_UX.get(
        status, ("warning", f"Trạng thái không xác định: {status}", "Xem log để biết thêm.")
    )
    return {"status": status, "level": level, "message": message, "action": action}


def collect_status_notices(result: dict) -> list[dict]:
    """Gom status chính + các status phụ suy ra từ trace để hiển thị đủ."""
    notices = [describe_status(result.get("status", "unknown"))]
    qs = result.get("query_set") or {}
    if qs.get("status") == "query_generation_unavailable" and result.get("status") != (
        "query_generation_unavailable"
    ):
        notices.append(describe_status("query_generation_unavailable"))
    child_trace = (result.get("trace") or {}).get("child_trace") or {}
    if child_trace.get("query_count_failed"):
        notices.append(describe_status("multi_query_partial"))
    return notices


# ---------------------------------------------------------------------------
# Tab 2 — Query fan-out
# ---------------------------------------------------------------------------


def query_cards(result: dict) -> list[dict]:
    """Card cho từng Q0..Qn: nguồn gốc, focus, số kết quả, latency, trạng thái."""
    qs = result.get("query_set") or {}
    trace = (result.get("trace") or {}).get("child_trace") or {}
    counts = trace.get("result_count_per_query", {})
    latencies = (trace.get("latency_ms") or {}).get("per_query_retrieval", {})
    failed = trace.get("failed_queries", {})

    cards = []
    for q in qs.get("queries", []):
        qid = q["query_id"]
        is_original = q.get("origin") == "original"
        if qid in failed:
            validation, result_count = "retrieval_failed", None
        elif qid in counts:
            validation, result_count = "ok", counts[qid]
        else:
            validation, result_count = "not_executed", None
        cards.append(
            {
                "query_id": qid,
                "text": q.get("text", ""),
                "origin": q.get("origin"),
                "is_original": is_original,
                "focus": q.get("focus"),
                "validation": validation,
                "error": failed.get(qid),
                "result_count": result_count,
                "latency_ms": latencies.get(qid),
            }
        )
    return cards


def query_child_matrix(result: dict, limit: int = 25) -> dict:
    """
    Ma trận: hàng = child, cột = Q0..Qn, ô = rank hoặc None.

    None hiển thị thành '—' và có nghĩa là "query đó KHÔNG tìm thấy child này",
    KHÔNG phải rank 0. Đây là khác biệt hình ảnh bắt buộc so với Buổi 08.
    """
    qs = result.get("query_set") or {}
    qids = [q["query_id"] for q in qs.get("queries", [])]
    rows = []
    for hit in (result.get("child_hits") or [])[:limit]:
        ranks = hit.get("per_query_ranks", {})
        rows.append(
            {
                "child_id": hit["child_id"],
                "multi_query_rank": hit.get("multi_query_rank"),
                "multi_query_rrf_score": hit.get("multi_query_rrf_score"),
                "support_query_count": hit.get("support_query_count"),
                "ranks": {qid: ranks.get(qid) for qid in qids},
                "snippet": _snippet(hit.get("text", "")),
            }
        )
    return {"query_ids": qids, "rows": rows,
            "legend": "Ô '—' = query đó không tìm thấy child này (không phải rank 0)."}


def _snippet(text: str, width: int = 120) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


# ---------------------------------------------------------------------------
# Tab 3 — Parent–Child Explorer
# ---------------------------------------------------------------------------


def parent_tree(result: dict) -> list[dict]:
    """
    Dữ liệu cây: parent -> supporting children -> query ranks.

    Ưu tiên `evidence` (đã rerank, có nhãn P#); nếu chưa rerank thì dùng
    `parent_candidates` để tab vẫn xem được sau lệnh parent-retrieve.
    """
    by_child = {c["child_id"]: c for c in (result.get("child_hits") or [])}
    parents = result.get("evidence") or result.get("parent_candidates") or []

    nodes = []
    for p in parents:
        if "parent_id" not in p:
            continue  # flat mode: không có cây parent
        sp = p.get("structural_path") or {}
        children = []
        for cid in p.get("supporting_child_ids", []):
            hit = by_child.get(cid, {})
            children.append(
                {
                    "child_id": cid,
                    "is_anchor": cid == p.get("anchor_child_id"),
                    "is_scoring": cid in (p.get("scoring_child_ids") or []),
                    "multi_query_rank": hit.get("multi_query_rank"),
                    "query_ranks": hit.get("per_query_ranks", {}),
                    "snippet": _snippet(hit.get("text", "")),
                }
            )
        rerank_rank = p.get("parent_rerank_rank")
        base_rank = p.get("parent_rank")
        nodes.append(
            {
                "label": p.get("label"),
                "accepted": p.get("accepted"),
                "parent_id": p["parent_id"],
                "path": " > ".join(v for v in (sp.get("chapter"), sp.get("article")) if v),
                "source": p.get("source"),
                "page_start": p.get("page_start"),
                "page_end": p.get("page_end"),
                "parent_rank": base_rank,
                "parent_rerank_rank": rerank_rank,
                "rank_movement": _rank_movement(base_rank, rerank_rank),
                "parent_rrf_score": p.get("parent_rrf_score"),
                "parent_rerank_score": p.get("parent_rerank_score"),
                "ambiguous": p.get("ambiguous", False),
                "warnings": list(p.get("warnings") or []),
                "char_count": len(p.get("text") or ""),
                "text": p.get("text", ""),
                "children": children,
            }
        )
    return nodes


def _rank_movement(before, after) -> str:
    """'#3 → #1 (▲2)'. Thiếu dữ liệu thì nói rõ chưa rerank, không đoán."""
    if before is None:
        return "—"
    if after is None:
        return f"#{before} (chưa rerank)"
    delta = before - after
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
    return f"#{before} → #{after} ({arrow}{abs(delta)})"


# ---------------------------------------------------------------------------
# Tab 4 — Mode comparison
# ---------------------------------------------------------------------------


def mode_comparison_rows(compare_result: dict) -> list[dict]:
    """
    Một hàng cho mỗi mode.

    KHÔNG kết luận mode nào thắng: bảng này không có gold labels, và flat mode
    trả child trong khi parent mode trả parent nên hai cột không cùng đơn vị.
    """
    rows = []
    per_mode = compare_result.get("per_mode", {})
    errors = compare_result.get("errors", {})

    for mode in compare_result.get("modes", list(per_mode) + list(errors)):
        if mode in errors:
            rows.append(
                {
                    "mode": mode, "status": "error", "error": errors[mode],
                    "unit": "parent" if mode.endswith("_parent") else "child",
                    "evidence_ids": [], "final_count": 0, "retrieved_child_count": 0,
                    "expanded_parent_count": 0, "context_chars": 0,
                    "expansion_factor": None, "unique_sources": 0, "unique_articles": 0,
                    "generation_api_calls": 0, "embedding_api_calls": 0,
                    "latency_ms": None, "warnings": [],
                }
            )
            continue

        res = per_mode[mode]
        is_parent = mode.endswith("_parent")
        final = res.get("reranked", [])
        ids = [(f["parent_id"] if is_parent else f["chunk_id"]) for f in final]

        sources = {f.get("source") for f in final if f.get("source")}
        articles = set()
        for f in final:
            sp = f.get("structural_path") or {}
            if sp.get("article"):
                articles.add((f.get("source"), sp["article"]))

        child_count = len(res.get("child_hits", []))
        parent_count = len(res.get("parent_candidates", []))
        context_chars = sum(len(f.get("text") or "") for f in final)
        child_chars = sum(len(h.get("text") or "") for h in res.get("child_hits", []))

        rows.append(
            {
                "mode": mode,
                "status": res.get("status"),
                "error": None,
                "unit": "parent" if is_parent else "child",
                "evidence_ids": ids,
                "final_count": len(final),
                "retrieved_child_count": child_count,
                "expanded_parent_count": parent_count,
                "context_chars": context_chars,
                "expansion_factor": (context_chars / child_chars) if child_chars else None,
                "unique_sources": len(sources),
                "unique_articles": len(articles),
                "generation_api_calls": res.get("generation_api_calls", 0),
                "embedding_api_calls": res.get("embedding_api_calls", 0),
                "latency_ms": (res.get("latency_ms") or {}).get("total"),
                "warnings": list(res.get("warnings") or []),
            }
        )
    return rows


COMPARISON_DISCLAIMER = (
    "Bảng này chỉ mô tả hành vi retrieval, KHÔNG kết luận mode nào tốt hơn: "
    "chưa có gold labels trong lượt chạy này, và flat mode trả child còn parent mode "
    "trả parent nên số lượng/độ dài không so trực tiếp được."
)


# ---------------------------------------------------------------------------
# Citation
# ---------------------------------------------------------------------------


def format_citations(result: dict) -> list[dict]:
    """Chuẩn hoá citation để hiển thị. Không bịa trường thiếu."""
    out = []
    for c in result.get("citations") or []:
        sp = c.get("structural_path") or {}
        path = " > ".join(v for v in (sp.get("chapter"), sp.get("article")) if v)
        pages = (
            f"tr.{c['page_start']}"
            if c.get("page_start") == c.get("page_end")
            else f"tr.{c.get('page_start')}–{c.get('page_end')}"
        )
        supporting = c.get("supporting_child_ids") or []
        out.append(
            {
                "evidence_id": c.get("evidence_id") or c.get("label"),
                "source": c.get("source"),
                "pages": pages,
                "path": path or "(không xác định được Chương/Điều)",
                "parent_id": c.get("parent_id"),
                "anchor_child_id": c.get("anchor_child_id") or c.get("chunk_id"),
                "supporting_child_count": len(supporting),
                "score_label": _score_label(c),
                "ambiguous": c.get("ambiguous", False),
                "warnings": list(c.get("warnings") or []),
            }
        )
    return out


def _score_label(c: dict) -> str:
    score = c.get("parent_rerank_score", c.get("rerank_score"))
    if score is None:
        return "—"
    return f"{score:.4f} (điểm chuẩn hoá của reranker, không phải xác suất đúng)"


# ---------------------------------------------------------------------------
# Tab 5 — Evaluation
# ---------------------------------------------------------------------------


def latest_report(reports_dir: Path = REPORTS_DIR) -> dict | None:
    """
    CHỈ ĐỌC report mới nhất. Không chạy evaluator, không tạo thư mục.
    Trả None nếu chưa có; file hỏng trả dict có 'error'.
    """
    rd = Path(reports_dir)
    if not rd.exists():
        return None
    files = sorted(rd.glob("*.json"))
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        payload = json.loads(newest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"path": str(newest), "error": f"Không đọc được report: {exc}"}
    return {"path": str(newest), "name": newest.name, "report": payload}


def evaluation_rows(report: dict) -> list[dict]:
    """Bảng metric theo mode từ report đã đọc."""
    rows = []
    for mode, m in (report.get("per_mode") or {}).items():
        rows.append(
            {
                "mode": mode,
                "child_recall": m.get("child_recall_at_k"),
                "parent_recall": m.get("parent_recall_at_k"),
                "mrr": m.get("mrr_at_k"),
                "ndcg": m.get("ndcg_at_k"),
                "latency_mean_ms": (m.get("latency_ms") or {}).get("mean"),
                "latency_p50_ms": (m.get("latency_ms") or {}).get("p50"),
                "context_chars_mean": m.get("context_chars_mean"),
            }
        )
    return rows


def gold_label_warning(report: dict) -> str | None:
    """Cảnh báo nếu gold labels còn cần người xác nhận."""
    n = report.get("needs_human_review_count")
    if n is None:
        questions = report.get("questions") or []
        n = sum(1 for q in questions if q.get("needs_human_review"))
    if n:
        return (
            f"{n} câu hỏi trong bộ gold labels đang ở trạng thái needs_human_review=true. "
            "Số liệu dưới đây chỉ dùng để tham khảo nội bộ, chưa đủ tin cậy để kết luận "
            "mode nào tốt hơn."
        )
    return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def sidebar_snapshot(config, hcfg, hierarchy_state: dict | None, collection_state: dict | None) -> dict:
    """
    Gom thông tin hiển thị ở thanh bên.

    API key CHỈ báo có/không — không bao giờ trả về giá trị, kể cả cắt ngắn.
    """
    manifest = (hierarchy_state or {}).get("manifest") or {}
    counts = manifest.get("counts", {})
    warn_counts = manifest.get("warning_counts", {})
    return {
        "gemini_key_present": bool(config.base.gemini_api_key),
        "embedding_model": config.base.embedding_model,
        "generation_model": config.base.generation_model,
        "reranker_model": config.reranker_model,
        "strategy": "hierarchical",
        "hierarchy_state": (hierarchy_state or {}).get("state", "missing"),
        "hierarchy_built_at": manifest.get("built_at"),
        "child_count": counts.get("children"),
        "parent_count": counts.get("parents"),
        "ambiguous_count": warn_counts.get("ambiguous_children"),
        "collection_state": (collection_state or {}).get("state", "unknown"),
        "collection_count": (collection_state or {}).get("count"),
        "config": {
            "MULTI_QUERY_COUNT": hcfg.multi_query_count,
            "PER_QUERY_CANDIDATES": hcfg.per_query_candidates,
            "PARENT_CANDIDATES": hcfg.parent_candidates,
            "FINAL_PARENT_TOP_K": hcfg.final_parent_top_k,
            "RERANK_MIN_SCORE": config.rerank_min_score,
        },
    }


# Giới hạn runtime cho widget thanh bên: nằm trong khoảng validator của
# load_hierarchy_config để người dùng không tạo được config sai.
RUNTIME_LIMITS = {
    "MULTI_QUERY_COUNT": (1, 5),
    "PER_QUERY_CANDIDATES": (1, 100),
    "PARENT_CANDIDATES": (1, 100),
    "FINAL_PARENT_TOP_K": (1, 100),
    "RERANK_MIN_SCORE": (0.0, 1.0),
}


def apply_runtime_overrides(config, hcfg, overrides: dict) -> list[str]:
    """
    Áp override từ widget vào bản sao config đang chạy.

    Giá trị ngoài khoảng hoặc sai ràng buộc bị TỪ CHỐI kèm lý do — widget không
    được phép tạo ra cấu hình mà CLI sẽ coi là không hợp lệ.
    """
    rejected = []
    for name, value in overrides.items():
        if name not in RUNTIME_LIMITS:
            rejected.append(f"{name}: không phải tham số chỉnh được lúc chạy.")
            continue
        low, high = RUNTIME_LIMITS[name]
        if value is None or not (low <= value <= high):
            rejected.append(f"{name}: {value} nằm ngoài khoảng {low}–{high}.")
            continue
        if name == "RERANK_MIN_SCORE":
            config.rerank_min_score = float(value)
        else:
            setattr(hcfg, name.lower(), int(value))

    if hcfg.final_parent_top_k > hcfg.parent_candidates:
        rejected.append(
            f"FINAL_PARENT_TOP_K ({hcfg.final_parent_top_k}) phải <= "
            f"PARENT_CANDIDATES ({hcfg.parent_candidates}) — giữ nguyên giá trị cũ."
        )
        hcfg.final_parent_top_k = min(hcfg.final_parent_top_k, hcfg.parent_candidates)
    return rejected


# Thao tác có thể TỐN TIỀN hoặc TỐN THỜI GIAN — phải do người dùng bấm, không
# bao giờ chạy lúc render trang.
COSTLY_ACTIONS = {
    "build_hierarchy": "Đọc lại toàn bộ chunk và ghi lại store (không gọi API).",
    "prepare_semantic": "GỌI Gemini Embedding API cho toàn bộ chunk — tốn quota.",
    "run_query": "Gọi Gemini (tối đa 2 generation call) và dùng cross-encoder.",
    "run_compare": "Chạy 4 mode retrieval; sinh query 1 lần; KHÔNG sinh câu trả lời.",
    "load_reranker": "Tải model cross-encoder ~2,27 GB ở lần đầu.",
}
