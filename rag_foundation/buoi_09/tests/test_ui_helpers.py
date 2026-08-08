"""tests/test_ui_helpers.py — Test helper giao diện (Bước 08).

Thuần Python: không trình duyệt, không import streamlit, không gọi API, không
tải model, không đọc `.env` thật.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ui_helpers as uh  # noqa: E402


def child_hit(cid, rank, ranks=None, text="nội dung child dài hơn một chút"):
    return {
        "child_id": cid, "text": text, "source": "s.pdf", "page_start": 1, "page_end": 1,
        "per_query_ranks": ranks or {"Q0": rank},
        "support_query_ids": list((ranks or {"Q0": rank}).keys()),
        "support_query_count": len(ranks or {"Q0": rank}),
        "multi_query_rank": rank, "multi_query_rrf_score": 1.0 / (60 + rank),
    }


def evidence(pid, label, parent_rank, rerank_rank, children, accepted=True, ambiguous=False):
    return {
        "label": label, "accepted": accepted, "parent_id": pid,
        "anchor_child_id": children[0], "scoring_child_ids": children[:2],
        "supporting_child_ids": children, "support_query_ids": ["Q0"],
        "source": "s.pdf", "page_start": 1, "page_end": 3,
        "structural_path": {"chapter": "Chương II", "article": "Điều 7"},
        "text": "toàn văn parent", "parent_rrf_score": 0.0321, "parent_rank": parent_rank,
        "parent_rerank_raw_score": 2.0, "parent_rerank_score": 0.88,
        "parent_rerank_rank": rerank_rank,
        "parent_rank_change": parent_rank - rerank_rank if rerank_rank else None,
        "ambiguous": ambiguous, "warnings": [],
    }


def sample_result(**over):
    res = {
        "status": "answered",
        "mode": "multi_parent",
        "original_question": "Điều 7 quy định gì?",
        "query_set": {
            "status": "ready",
            "queries": [
                {"query_id": "Q0", "text": "Điều 7 quy định gì?", "origin": "original",
                 "focus": "original_intent"},
                {"query_id": "Q1", "text": "nội dung Điều 7", "origin": "generated",
                 "focus": "paraphrase"},
                {"query_id": "Q2", "text": "vốn tự có gồm gì", "origin": "generated",
                 "focus": "missing_aspect"},
            ],
        },
        "child_hits": [
            child_hit("c1", 1, {"Q0": 1, "Q1": 2}),
            child_hit("c2", 2, {"Q1": 1}),
            child_hit("c3", 3, {"Q0": 5, "Q1": 4, "Q2": 1}),
        ],
        "parent_candidates": [],
        "evidence": [evidence("p1", "P1", 2, 1, ["c1", "c3"]),
                     evidence("p2", None, 1, 2, ["c2"], accepted=False)],
        "accepted_evidence": [],
        "answer": "Nội dung. [P1]",
        "citations": [{
            "evidence_id": "P1", "parent_id": "p1", "anchor_child_id": "c1",
            "supporting_child_ids": ["c1", "c3"], "source": "s.pdf",
            "page_start": 1, "page_end": 3,
            "structural_path": {"chapter": "Chương II", "article": "Điều 7"},
            "parent_rerank_score": 0.8812, "ambiguous": False, "warnings": [],
        }],
        "warnings": [],
        "identities": {},
        "trace": {
            "generation_api_calls": 2, "embedding_api_calls": 3, "accepted_count": 1,
            "child_trace": {
                "result_count_per_query": {"Q0": 12, "Q1": 12, "Q2": 12},
                "failed_queries": {}, "query_count_failed": 0,
                "latency_ms": {"per_query_retrieval": {"Q0": 100.0, "Q1": 120.0, "Q2": 90.0}},
            },
            "latency_ms": {"total": 500.0},
        },
    }
    res.update(over)
    return res


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------


class StatusTests(unittest.TestCase):
    def test_all_required_statuses_mapped(self):
        for s in ("hierarchy_not_ready", "collection_not_ready", "query_generation_unavailable",
                  "multi_query_partial", "reranker_unavailable", "insufficient_evidence",
                  "generation_error"):
            d = uh.describe_status(s)
            self.assertIn(d["level"], ("success", "warning", "error"))
            self.assertTrue(d["message"])
            self.assertTrue(d["action"], f"{s} phải có hướng xử lý")

    def test_unknown_status_does_not_crash(self):
        d = uh.describe_status("cái_gì_đó_lạ")
        self.assertEqual(d["level"], "warning")
        self.assertIn("cái_gì_đó_lạ", d["message"])

    def test_error_levels_correct(self):
        self.assertEqual(uh.describe_status("reranker_unavailable")["level"], "error")
        self.assertEqual(uh.describe_status("insufficient_evidence")["level"], "warning")
        self.assertEqual(uh.describe_status("answered")["level"], "success")

    def test_no_stack_trace_or_key_in_messages(self):
        for s in uh.STATUS_UX:
            d = uh.describe_status(s)
            blob = d["message"] + d["action"]
            self.assertNotIn("Traceback", blob)
            self.assertNotIn("AIza", blob)

    def test_collect_notices_adds_partial(self):
        res = sample_result()
        res["trace"]["child_trace"]["query_count_failed"] = 1
        notices = uh.collect_status_notices(res)
        self.assertIn("multi_query_partial", [n["status"] for n in notices])

    def test_collect_notices_adds_generation_unavailable(self):
        res = sample_result()
        res["query_set"]["status"] = "query_generation_unavailable"
        notices = uh.collect_status_notices(res)
        self.assertIn("query_generation_unavailable", [n["status"] for n in notices])

    def test_collect_notices_no_duplicate_primary(self):
        res = sample_result(status="query_generation_unavailable")
        res["query_set"]["status"] = "query_generation_unavailable"
        statuses = [n["status"] for n in uh.collect_status_notices(res)]
        self.assertEqual(statuses.count("query_generation_unavailable"), 1)


# ---------------------------------------------------------------------------
# Query fan-out
# ---------------------------------------------------------------------------


class QueryCardTests(unittest.TestCase):
    def test_card_per_query(self):
        cards = uh.query_cards(sample_result())
        self.assertEqual([c["query_id"] for c in cards], ["Q0", "Q1", "Q2"])

    def test_q0_flagged_original(self):
        cards = uh.query_cards(sample_result())
        self.assertTrue(cards[0]["is_original"])
        self.assertFalse(cards[1]["is_original"])

    def test_counts_and_latency_attached(self):
        cards = uh.query_cards(sample_result())
        self.assertEqual(cards[0]["result_count"], 12)
        self.assertEqual(cards[1]["latency_ms"], 120.0)

    def test_failed_query_marked_not_zero(self):
        res = sample_result()
        res["trace"]["child_trace"]["failed_queries"] = {"Q1": "mạng lỗi"}
        del res["trace"]["child_trace"]["result_count_per_query"]["Q1"]
        cards = {c["query_id"]: c for c in uh.query_cards(res)}
        self.assertEqual(cards["Q1"]["validation"], "retrieval_failed")
        self.assertIsNone(cards["Q1"]["result_count"], "lỗi KHÔNG được hiển thị là 0 kết quả")

    def test_missing_query_set_no_crash(self):
        self.assertEqual(uh.query_cards({"status": "x"}), [])


class MatrixTests(unittest.TestCase):
    def test_columns_are_all_queries(self):
        m = uh.query_child_matrix(sample_result())
        self.assertEqual(m["query_ids"], ["Q0", "Q1", "Q2"])

    def test_missing_rank_is_none_not_zero(self):
        m = uh.query_child_matrix(sample_result())
        row = {r["child_id"]: r for r in m["rows"]}["c2"]
        self.assertIsNone(row["ranks"]["Q0"])
        self.assertIsNone(row["ranks"]["Q2"])
        self.assertEqual(row["ranks"]["Q1"], 1)

    def test_legend_explains_dash(self):
        m = uh.query_child_matrix(sample_result())
        self.assertIn("không phải rank 0", m["legend"])

    def test_limit_respected(self):
        res = sample_result()
        res["child_hits"] = [child_hit(f"c{i}", i) for i in range(1, 40)]
        self.assertEqual(len(uh.query_child_matrix(res, limit=5)["rows"]), 5)

    def test_snippet_truncated(self):
        res = sample_result()
        res["child_hits"] = [child_hit("c1", 1, text="x" * 500)]
        snippet = uh.query_child_matrix(res)["rows"][0]["snippet"]
        self.assertLessEqual(len(snippet), 120)
        self.assertTrue(snippet.endswith("…"))


# ---------------------------------------------------------------------------
# Parent tree
# ---------------------------------------------------------------------------


class ParentTreeTests(unittest.TestCase):
    def test_node_per_parent(self):
        nodes = uh.parent_tree(sample_result())
        self.assertEqual([n["parent_id"] for n in nodes], ["p1", "p2"])

    def test_children_carry_query_ranks(self):
        nodes = uh.parent_tree(sample_result())
        c1 = nodes[0]["children"][0]
        self.assertEqual(c1["child_id"], "c1")
        self.assertEqual(c1["query_ranks"], {"Q0": 1, "Q1": 2})

    def test_anchor_and_scoring_flags(self):
        nodes = uh.parent_tree(sample_result())
        self.assertTrue(nodes[0]["children"][0]["is_anchor"])
        self.assertTrue(all(c["is_scoring"] for c in nodes[0]["children"]))

    def test_rank_movement_up(self):
        nodes = uh.parent_tree(sample_result())
        self.assertEqual(nodes[0]["rank_movement"], "#2 → #1 (▲1)")

    def test_rank_movement_down_and_equal(self):
        self.assertEqual(uh._rank_movement(1, 3), "#1 → #3 (▼2)")
        self.assertEqual(uh._rank_movement(2, 2), "#2 → #2 (=0)")

    def test_rank_movement_before_rerank(self):
        self.assertEqual(uh._rank_movement(4, None), "#4 (chưa rerank)")
        self.assertEqual(uh._rank_movement(None, None), "—")

    def test_flat_mode_gives_empty_tree(self):
        res = sample_result(evidence=[{"chunk_id": "c1", "text": "x"}], parent_candidates=[])
        self.assertEqual(uh.parent_tree(res), [])

    def test_falls_back_to_parent_candidates(self):
        res = sample_result(evidence=[], parent_candidates=[
            dict(evidence("p9", None, 1, None, ["c1"]), label=None)])
        nodes = uh.parent_tree(res)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["parent_id"], "p9")

    def test_ambiguous_surfaced(self):
        res = sample_result(evidence=[evidence("p1", "P1", 1, 1, ["c1"], ambiguous=True)])
        self.assertTrue(uh.parent_tree(res)[0]["ambiguous"])


# ---------------------------------------------------------------------------
# Mode comparison
# ---------------------------------------------------------------------------


def cmp_result():
    def mode_res(unit, n_child, n_parent, final):
        return {
            "status": "ready",
            "child_hits": [child_hit(f"c{i}", i, text="y" * 100) for i in range(1, n_child + 1)],
            "parent_candidates": [evidence(f"p{i}", None, i, None, ["c1"])
                                  for i in range(1, n_parent + 1)],
            "reranked": final,
            "generation_api_calls": 1, "embedding_api_calls": 3,
            "latency_ms": {"total": 250.0}, "warnings": [],
        }

    child_final = [{"chunk_id": "c1", "text": "z" * 200, "source": "s.pdf"}]
    parent_final = [{"parent_id": "p1", "text": "z" * 900, "source": "s.pdf",
                     "structural_path": {"article": "Điều 7"}}]
    return {
        "modes": ["single_flat", "multi_flat", "single_parent", "multi_parent"],
        "per_mode": {
            "single_flat": mode_res("child", 5, 0, child_final),
            "multi_flat": mode_res("child", 8, 0, child_final),
            "single_parent": mode_res("parent", 5, 3, parent_final),
        },
        "errors": {"multi_parent": "hierarchy_not_ready: thiếu file"},
    }


class ComparisonTests(unittest.TestCase):
    def test_row_per_mode_including_errors(self):
        rows = uh.mode_comparison_rows(cmp_result())
        self.assertEqual([r["mode"] for r in rows],
                         ["single_flat", "multi_flat", "single_parent", "multi_parent"])

    def test_unit_labelled(self):
        rows = {r["mode"]: r for r in uh.mode_comparison_rows(cmp_result())}
        self.assertEqual(rows["single_flat"]["unit"], "child")
        self.assertEqual(rows["single_parent"]["unit"], "parent")

    def test_error_mode_row_is_safe(self):
        rows = {r["mode"]: r for r in uh.mode_comparison_rows(cmp_result())}
        r = rows["multi_parent"]
        self.assertEqual(r["status"], "error")
        self.assertIn("hierarchy_not_ready", r["error"])
        self.assertEqual(r["final_count"], 0)

    def test_expansion_factor_computed(self):
        rows = {r["mode"]: r for r in uh.mode_comparison_rows(cmp_result())}
        # parent: 900 ký tự context / (5 child × 100) = 1.8
        self.assertAlmostEqual(rows["single_parent"]["expansion_factor"], 1.8, places=6)

    def test_counts_child_and_parent(self):
        rows = {r["mode"]: r for r in uh.mode_comparison_rows(cmp_result())}
        self.assertEqual(rows["multi_flat"]["retrieved_child_count"], 8)
        self.assertEqual(rows["single_parent"]["expanded_parent_count"], 3)

    def test_api_calls_separated(self):
        rows = {r["mode"]: r for r in uh.mode_comparison_rows(cmp_result())}
        self.assertEqual(rows["single_flat"]["generation_api_calls"], 1)
        self.assertEqual(rows["single_flat"]["embedding_api_calls"], 3)

    def test_unique_sources_and_articles(self):
        rows = {r["mode"]: r for r in uh.mode_comparison_rows(cmp_result())}
        self.assertEqual(rows["single_parent"]["unique_sources"], 1)
        self.assertEqual(rows["single_parent"]["unique_articles"], 1)

    def test_disclaimer_refuses_to_declare_winner(self):
        self.assertIn("KHÔNG kết luận", uh.COMPARISON_DISCLAIMER)
        self.assertIn("gold labels", uh.COMPARISON_DISCLAIMER)


# ---------------------------------------------------------------------------
# Citation formatting
# ---------------------------------------------------------------------------


class CitationFormatTests(unittest.TestCase):
    def test_basic_fields(self):
        c = uh.format_citations(sample_result())[0]
        self.assertEqual(c["evidence_id"], "P1")
        self.assertEqual(c["parent_id"], "p1")
        self.assertEqual(c["anchor_child_id"], "c1")
        self.assertEqual(c["supporting_child_count"], 2)

    def test_page_range_formatting(self):
        res = sample_result()
        res["citations"][0]["page_end"] = 1
        self.assertEqual(uh.format_citations(res)[0]["pages"], "tr.1")
        res["citations"][0]["page_end"] = 5
        self.assertEqual(uh.format_citations(res)[0]["pages"], "tr.1–5")

    def test_score_label_says_not_probability(self):
        c = uh.format_citations(sample_result())[0]
        self.assertIn("không phải xác suất", c["score_label"])

    def test_missing_score_shown_as_dash(self):
        res = sample_result()
        res["citations"][0].pop("parent_rerank_score")
        self.assertEqual(uh.format_citations(res)[0]["score_label"], "—")

    def test_missing_structural_path_labelled(self):
        res = sample_result()
        res["citations"][0]["structural_path"] = {}
        self.assertIn("không xác định", uh.format_citations(res)[0]["path"])

    def test_no_citations_returns_empty(self):
        self.assertEqual(uh.format_citations({"citations": []}), [])


# ---------------------------------------------------------------------------
# Evaluation tab
# ---------------------------------------------------------------------------


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_missing_dir_returns_none(self):
        self.assertIsNone(uh.latest_report(self.dir / "khong_co"))

    def test_empty_dir_returns_none(self):
        self.assertIsNone(uh.latest_report(self.dir))

    def test_reads_newest(self):
        import os
        import time

        (self.dir / "a.json").write_text(json.dumps({"tag": "cu"}), encoding="utf-8")
        time.sleep(0.01)
        (self.dir / "b.json").write_text(json.dumps({"tag": "moi"}), encoding="utf-8")
        os.utime(self.dir / "b.json", (time.time() + 10, time.time() + 10))
        self.assertEqual(uh.latest_report(self.dir)["report"]["tag"], "moi")

    def test_broken_json_reports_error_not_crash(self):
        (self.dir / "x.json").write_text("{ hỏng", encoding="utf-8")
        out = uh.latest_report(self.dir)
        self.assertIn("error", out)

    def test_does_not_create_directory(self):
        target = self.dir / "chua_ton_tai"
        uh.latest_report(target)
        self.assertFalse(target.exists(), "tab evaluation phải chỉ đọc")

    def test_evaluation_rows(self):
        report = {"per_mode": {"multi_parent": {
            "child_recall_at_k": 0.42, "parent_recall_at_k": 0.55,
            "mrr_at_k": 0.31, "ndcg_at_k": 0.38,
            "latency_ms": {"mean": 900.0, "p50": 850.0}, "context_chars_mean": 5000}}}
        row = uh.evaluation_rows(report)[0]
        self.assertEqual(row["mode"], "multi_parent")
        self.assertEqual(row["parent_recall"], 0.55)
        self.assertEqual(row["latency_p50_ms"], 850.0)

    def test_gold_label_warning_from_count(self):
        self.assertIn("10", uh.gold_label_warning({"needs_human_review_count": 10}))

    def test_gold_label_warning_from_questions(self):
        report = {"questions": [{"needs_human_review": True}, {"needs_human_review": False}]}
        self.assertIsNotNone(uh.gold_label_warning(report))

    def test_no_warning_when_reviewed(self):
        self.assertIsNone(uh.gold_label_warning({"needs_human_review_count": 0}))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


class _FakeBase:
    gemini_api_key = "AIza-KEY-THAT-MUST-NOT-LEAK"
    embedding_model = "emb-model"
    generation_model = "gen-model"


class _FakeConfig:
    base = _FakeBase()
    reranker_model = "rr-model"
    rerank_min_score = 0.5


class _FakeHcfg:
    multi_query_count = 3
    per_query_candidates = 12
    parent_candidates = 10
    final_parent_top_k = 3


class SidebarTests(unittest.TestCase):
    def test_key_never_exposed(self):
        snap = uh.sidebar_snapshot(_FakeConfig(), _FakeHcfg(), None, None)
        blob = json.dumps(snap, ensure_ascii=False)
        self.assertNotIn("AIza", blob)
        self.assertTrue(snap["gemini_key_present"])

    def test_key_absent_reported_false(self):
        cfg = _FakeConfig()
        cfg.base = type("B", (), dict(vars(_FakeBase)))()
        cfg.base.gemini_api_key = ""
        cfg.base.embedding_model = "e"
        cfg.base.generation_model = "g"
        self.assertFalse(uh.sidebar_snapshot(cfg, _FakeHcfg(), None, None)["gemini_key_present"])

    def test_counts_from_manifest(self):
        state = {"state": "ready", "manifest": {
            "built_at": "2026-08-08T00:00:00Z",
            "counts": {"children": 399, "parents": 45},
            "warning_counts": {"ambiguous_children": 106}}}
        snap = uh.sidebar_snapshot(_FakeConfig(), _FakeHcfg(), state, {"state": "ready", "count": 399})
        self.assertEqual(snap["child_count"], 399)
        self.assertEqual(snap["parent_count"], 45)
        self.assertEqual(snap["ambiguous_count"], 106)
        self.assertEqual(snap["collection_state"], "ready")

    def test_missing_state_defaults(self):
        snap = uh.sidebar_snapshot(_FakeConfig(), _FakeHcfg(), None, None)
        self.assertEqual(snap["hierarchy_state"], "missing")
        self.assertIsNone(snap["child_count"])


class RuntimeOverrideTests(unittest.TestCase):
    def test_valid_override_applied(self):
        cfg, h = _FakeConfig(), _FakeHcfg()
        rejected = uh.apply_runtime_overrides(cfg, h, {"MULTI_QUERY_COUNT": 5})
        self.assertEqual(rejected, [])
        self.assertEqual(h.multi_query_count, 5)

    def test_out_of_range_rejected(self):
        cfg, h = _FakeConfig(), _FakeHcfg()
        rejected = uh.apply_runtime_overrides(cfg, h, {"MULTI_QUERY_COUNT": 99})
        self.assertTrue(rejected)
        self.assertEqual(h.multi_query_count, 3, "giá trị sai không được ghi đè")

    def test_unknown_param_rejected(self):
        cfg, h = _FakeConfig(), _FakeHcfg()
        rejected = uh.apply_runtime_overrides(cfg, h, {"PARENT_MAX_CHARS": 5000})
        self.assertTrue(any("không phải tham số" in r for r in rejected))

    def test_final_k_cannot_exceed_candidates(self):
        cfg, h = _FakeConfig(), _FakeHcfg()
        rejected = uh.apply_runtime_overrides(
            cfg, h, {"PARENT_CANDIDATES": 3, "FINAL_PARENT_TOP_K": 9})
        self.assertTrue(any("FINAL_PARENT_TOP_K" in r for r in rejected))
        self.assertLessEqual(h.final_parent_top_k, h.parent_candidates)

    def test_rerank_min_score_float(self):
        cfg, h = _FakeConfig(), _FakeHcfg()
        uh.apply_runtime_overrides(cfg, h, {"RERANK_MIN_SCORE": 0.75})
        self.assertAlmostEqual(cfg.rerank_min_score, 0.75)


class CostlyActionTests(unittest.TestCase):
    def test_all_costly_actions_documented(self):
        for key in ("build_hierarchy", "prepare_semantic", "run_query", "run_compare",
                    "load_reranker"):
            self.assertIn(key, uh.COSTLY_ACTIONS)
            self.assertTrue(uh.COSTLY_ACTIONS[key])

    def test_helpers_do_not_import_streamlit(self):
        source = (Path(uh.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("import streamlit", source)


if __name__ == "__main__":
    unittest.main()
