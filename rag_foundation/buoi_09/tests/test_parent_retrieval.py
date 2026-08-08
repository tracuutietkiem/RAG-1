"""tests/test_parent_retrieval.py — Test Parent–Child Retrieval (Bước 06).

Offline hoàn toàn: hierarchy store dựng trong thư mục tạm từ fixture, hybrid
retriever và query generator đều giả lập. Không mạng, không Chroma, không model.
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
import advanced_rag as ar  # noqa: E402
import hierarchical_rag as hr  # noqa: E402
import rag  # noqa: E402

from test_hierarchy import write_env  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def hit(child_id, rank, text="nội dung child", support=("Q0",), per_query=None):
    """Một child hit như đầu ra của cross_query_rrf."""
    return {
        "child_id": child_id,
        "text": text,
        "source": "s.pdf",
        "page_start": 1,
        "page_end": 1,
        "support_query_ids": list(support),
        "per_query_ranks": per_query or {q: rank for q in support},
        "per_query_trace": {},
        "multi_query_rrf_score": 1.0 / (60 + rank),
        "support_query_count": len(support),
        "best_query_rank": rank,
        "multi_query_rank": rank,
    }


def child_rec(child_id, parent_id, ambiguous=False):
    return {"child_id": child_id, "parent_id": parent_id, "ambiguous": ambiguous,
            "source": "s.pdf", "text": "x", "warnings": []}


def parent_rec(parent_id, text="parent context", p1=1, p2=2, warnings=None):
    return {
        "parent_id": parent_id, "source": "s.pdf", "page_start": p1, "page_end": p2,
        "text": text, "char_count": len(text), "article_key": "Điều 1", "window_index": 1,
        "child_ids": [], "structural_path": {"chapter": "Chương I", "article": "Điều 1"},
        "ambiguous_child_count": 0, "warnings": list(warnings or []),
    }


class ParentBase(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        env = write_env(self.work / ".env")
        self.config = ar.load_advanced_config(env)
        self.hcfg = hr.load_hierarchy_config(env)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def cfg(self, **over):
        self._n = getattr(self, "_n", 0) + 1
        env = write_env(self.work / f"override_{self._n}.env", **over)
        return hr.load_hierarchy_config(env)


# ---------------------------------------------------------------------------
# 1. Child -> parent mapping
# ---------------------------------------------------------------------------


class MappingTests(ParentBase):
    def test_child_maps_to_correct_parent(self):
        children = {"c1": child_rec("c1", "p1"), "c2": child_rec("c2", "p2")}
        parents = {"p1": parent_rec("p1"), "p2": parent_rec("p2")}
        m = hr.map_children_to_parents([hit("c1", 1), hit("c2", 2)], children, parents)
        self.assertEqual([x["parent_id"] for x in m], ["p1", "p2"])

    def test_missing_child_fails_with_id(self):
        with self.assertRaises(hr.HierarchyError) as ctx:
            hr.map_children_to_parents([hit("ghost", 1)], {}, {})
        self.assertIn("ghost", str(ctx.exception))

    def test_missing_parent_fails_with_id(self):
        children = {"c1": child_rec("c1", "p_missing")}
        with self.assertRaises(hr.HierarchyError) as ctx:
            hr.map_children_to_parents([hit("c1", 1)], children, {})
        self.assertIn("p_missing", str(ctx.exception))

    def test_child_without_parent_id_fails(self):
        children = {"c1": {"child_id": "c1", "ambiguous": False}}
        with self.assertRaises(hr.HierarchyError):
            hr.map_children_to_parents([hit("c1", 1)], children, {"p1": parent_rec("p1")})


# ---------------------------------------------------------------------------
# 2. Hierarchy status gate
# ---------------------------------------------------------------------------


class StatusGateTests(ParentBase):
    def test_missing_store_raises_not_ready(self):
        with self.assertRaises(hr.HierarchyNotReadyError) as ctx:
            hr.require_hierarchy_ready(self.hcfg, chunks_dir=FIXTURES,
                                       hierarchy_dir=self.work / "nope")
        self.assertIn("hierarchy_not_ready", str(ctx.exception))
        self.assertIn("build-hierarchy", str(ctx.exception))

    def test_stale_store_raises_not_ready(self):
        hdir = self.work / "h"
        hr.build_hierarchy(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=hdir)
        other = self.cfg(PARENT_MAX_CHARS="9000")
        with self.assertRaises(hr.HierarchyNotReadyError) as ctx:
            hr.require_hierarchy_ready(other, chunks_dir=FIXTURES, hierarchy_dir=hdir)
        self.assertEqual(ctx.exception.status["state"], "stale")

    def test_query_does_not_build_store(self):
        hdir = self.work / "never"
        with self.assertRaises(hr.HierarchyNotReadyError):
            hr.parent_retrieval("Điều 7?", self.config, self.hcfg,
                                chunks_dir=FIXTURES, hierarchy_dir=hdir,
                                child_result={"child_hits": [], "status": "ready",
                                              "query_set": {}, "trace": {}, "warnings": []})
        self.assertFalse(hdir.exists(), "query KHÔNG được tự tạo store")

    def test_ready_store_passes(self):
        hdir = self.work / "h"
        hr.build_hierarchy(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=hdir)
        st = hr.require_hierarchy_ready(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=hdir)
        self.assertEqual(st["state"], "ready")


# ---------------------------------------------------------------------------
# 3. Công thức aggregation
# ---------------------------------------------------------------------------


class AggregationTests(ParentBase):
    def setUp(self):
        super().setUp()
        self.children = {f"c{i}": child_rec(f"c{i}", "p1") for i in range(1, 8)}
        self.parents = {"p1": parent_rec("p1")}

    def test_formula_hand_computed(self):
        """child rank 1 và 3, K=60: 1/61 + 1/63 = 0.016393442 + 0.015873016 = 0.032266458"""
        hits = [hit("c1", 1), hit("c2", 3)]
        agg = hr.aggregate_parents(hits, self.children, self.parents, self.hcfg)
        expected = 1 / 61 + 1 / 63
        self.assertAlmostEqual(agg["parents"][0]["parent_rrf_score"], expected, places=12)
        self.assertAlmostEqual(expected, 0.032266458, places=9)

    def test_score_child_limit_caps_contribution(self):
        """PARENT_SCORE_CHILD_LIMIT=3: child thứ 4, 5 KHÔNG cộng điểm."""
        hits = [hit(f"c{i}", i) for i in range(1, 6)]
        agg = hr.aggregate_parents(hits, self.children, self.parents, self.hcfg)
        p = agg["parents"][0]
        self.assertEqual(len(p["scoring_child_ids"]), 3)
        self.assertAlmostEqual(p["parent_rrf_score"], 1 / 61 + 1 / 62 + 1 / 63, places=12)
        self.assertEqual(len(p["supporting_child_ids"]), 5)

    def test_scoring_takes_best_ranks(self):
        hits = [hit("c1", 9), hit("c2", 2), hit("c3", 7), hit("c4", 1)]
        agg = hr.aggregate_parents(hits, self.children, self.parents, self.hcfg)
        self.assertEqual(agg["parents"][0]["scoring_child_ids"], ["c4", "c2", "c3"])

    def test_raw_mq_score_not_added(self):
        """Đổi multi_query_rrf_score nhưng giữ rank -> parent score không đổi."""
        h1 = hit("c1", 1)
        h1["multi_query_rrf_score"] = 999.0
        a = hr.aggregate_parents([h1], self.children, self.parents, self.hcfg)
        h2 = hit("c1", 1)
        h2["multi_query_rrf_score"] = 0.00001
        b = hr.aggregate_parents([h2], self.children, self.parents, self.hcfg)
        self.assertAlmostEqual(a["parents"][0]["parent_rrf_score"],
                               b["parents"][0]["parent_rrf_score"], places=12)

    def test_anchor_is_best_ranked_child(self):
        hits = [hit("c1", 5), hit("c2", 2), hit("c3", 8)]
        agg = hr.aggregate_parents(hits, self.children, self.parents, self.hcfg)
        self.assertEqual(agg["parents"][0]["anchor_child_id"], "c2")
        self.assertEqual(agg["parents"][0]["best_child_rank"], 2)

    def test_support_query_ids_union(self):
        hits = [hit("c1", 1, support=("Q0",)), hit("c2", 2, support=("Q1", "Q2"))]
        agg = hr.aggregate_parents(hits, self.children, self.parents, self.hcfg)
        self.assertEqual(agg["parents"][0]["support_query_ids"], ["Q0", "Q1", "Q2"])

    def test_parent_deduplicated(self):
        """5 child cùng parent -> đúng 1 parent candidate."""
        hits = [hit(f"c{i}", i) for i in range(1, 6)]
        agg = hr.aggregate_parents(hits, self.children, self.parents, self.hcfg)
        self.assertEqual(len(agg["parents"]), 1)
        self.assertEqual(agg["all_parent_count"], 1)

    def test_ambiguous_flag_propagates(self):
        children = {"c1": child_rec("c1", "p1", ambiguous=True)}
        agg = hr.aggregate_parents([hit("c1", 1)], children, self.parents, self.hcfg)
        self.assertTrue(agg["parents"][0]["ambiguous"])
        self.assertTrue(any("ambiguous_child" in w for w in agg["parents"][0]["warnings"]))


# ---------------------------------------------------------------------------
# 4. Sort, tie-break, candidate limit
# ---------------------------------------------------------------------------


class SortTests(ParentBase):
    def _many(self, n):
        children = {f"c{i}": child_rec(f"c{i}", f"p{i}") for i in range(1, n + 1)}
        parents = {f"p{i}": parent_rec(f"p{i}") for i in range(1, n + 1)}
        return children, parents

    def test_sorted_by_score_desc(self):
        children, parents = self._many(3)
        hits = [hit("c1", 5), hit("c2", 1), hit("c3", 3)]
        agg = hr.aggregate_parents(hits, children, parents, self.hcfg)
        self.assertEqual([p["parent_id"] for p in agg["parents"]], ["p2", "p3", "p1"])
        self.assertEqual([p["parent_rank"] for p in agg["parents"]], [1, 2, 3])

    def test_tie_break_by_support_then_rank_then_id(self):
        """Cùng score: nhiều query hỗ trợ hơn thắng."""
        children = {"a1": child_rec("a1", "pA"), "b1": child_rec("b1", "pB")}
        parents = {"pA": parent_rec("pA"), "pB": parent_rec("pB")}
        hits = [hit("a1", 1, support=("Q0", "Q1")), hit("b1", 1, support=("Q0",))]
        agg = hr.aggregate_parents(hits, children, parents, self.hcfg)
        self.assertEqual(agg["parents"][0]["parent_id"], "pA")

    def test_tie_break_final_by_parent_id(self):
        children = {"z1": child_rec("z1", "pZ"), "a1": child_rec("a1", "pA")}
        parents = {"pZ": parent_rec("pZ"), "pA": parent_rec("pA")}
        hits = [hit("z1", 1), hit("a1", 1)]
        r1 = [p["parent_id"] for p in
              hr.aggregate_parents(hits, children, parents, self.hcfg)["parents"]]
        r2 = [p["parent_id"] for p in
              hr.aggregate_parents(list(reversed(hits)), children, parents, self.hcfg)["parents"]]
        self.assertEqual(r1, r2, "kết quả phải độc lập thứ tự đầu vào")
        self.assertEqual(r1, ["pA", "pZ"])

    def test_candidate_limit_applied(self):
        hcfg = self.cfg(PARENT_CANDIDATES="3", FINAL_PARENT_TOP_K="3")
        children, parents = self._many(6)
        hits = [hit(f"c{i}", i) for i in range(1, 7)]
        agg = hr.aggregate_parents(hits, children, parents, hcfg)
        self.assertEqual(len(agg["parents"]), 3)
        self.assertEqual(agg["all_parent_count"], 6)
        self.assertEqual(len(agg["dropped_by_candidate_limit"]), 3)


# ---------------------------------------------------------------------------
# 5. Context budget
# ---------------------------------------------------------------------------


class BudgetTests(ParentBase):
    def test_cuts_only_at_parent_boundary(self):
        hcfg = self.cfg(TOTAL_CONTEXT_MAX_CHARS="2500", PARENT_MAX_CHARS="2000")
        parents = [dict(parent_rec(f"p{i}", text="x" * 1000), parent_rank=i) for i in range(1, 5)]
        out = hr.apply_context_budget(parents, hcfg)
        self.assertEqual(len(out["selected"]), 2)
        self.assertEqual(out["total_chars"], 2000)
        for p in out["selected"]:
            self.assertEqual(len(p["text"]), 1000, "không được cắt giữa parent")

    def test_dropped_parents_recorded(self):
        hcfg = self.cfg(TOTAL_CONTEXT_MAX_CHARS="1500", PARENT_MAX_CHARS="1200")
        parents = [dict(parent_rec(f"p{i}", text="x" * 1000), parent_rank=i) for i in range(1, 4)]
        out = hr.apply_context_budget(parents, hcfg)
        self.assertEqual(len(out["selected"]), 1)
        self.assertEqual([d["parent_id"] for d in out["dropped_by_budget"]], ["p2", "p3"])
        self.assertEqual(out["dropped_by_budget"][0]["reason"], "context_budget")

    def test_oversized_first_parent_kept_with_warning(self):
        hcfg = self.cfg(TOTAL_CONTEXT_MAX_CHARS="1000", PARENT_MAX_CHARS="1000")
        parents = [dict(parent_rec("big", text="x" * 5000), parent_rank=1),
                   dict(parent_rec("p2", text="y" * 100), parent_rank=2)]
        out = hr.apply_context_budget(parents, hcfg)
        self.assertEqual([p["parent_id"] for p in out["selected"]], ["big"])
        self.assertTrue(any("oversized_first_parent" in w for w in out["warnings"]))
        self.assertNotEqual(out["selected"], [], "không được trả context rỗng")

    def test_duplicate_parent_not_counted_twice(self):
        hcfg = self.cfg(TOTAL_CONTEXT_MAX_CHARS="2500", PARENT_MAX_CHARS="2000")
        p = dict(parent_rec("dup", text="x" * 1000), parent_rank=1)
        out = hr.apply_context_budget([p, dict(p), dict(p)], hcfg)
        self.assertEqual(len(out["selected"]), 1)
        self.assertEqual(out["total_chars"], 1000)

    def test_all_fit_when_budget_large(self):
        parents = [dict(parent_rec(f"p{i}", text="x" * 100), parent_rank=i) for i in range(1, 6)]
        out = hr.apply_context_budget(parents, self.hcfg)
        self.assertEqual(len(out["selected"]), 5)
        self.assertEqual(out["warnings"], [])


# ---------------------------------------------------------------------------
# 6. Pipeline end-to-end (store thật từ fixture, retrieval giả lập)
# ---------------------------------------------------------------------------


class PipelineTests(ParentBase):
    def setUp(self):
        super().setUp()
        self.hdir = self.work / "h"
        hr.build_hierarchy(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=self.hdir)
        self.children, self.parents_by_id, _ = hr.load_hierarchy_store(self.hdir)
        self.child_ids = sorted(self.children)

    def _child_result(self, n=4, status="ready"):
        hits = []
        for i, cid in enumerate(self.child_ids[:n], start=1):
            hits.append(hit(cid, i, text=self.children[cid]["text"],
                            support=("Q0", "Q1") if i % 2 else ("Q0",)))
        return {
            "status": status, "child_hits": hits, "warnings": [],
            "query_set": {"queries": [
                {"query_id": "Q0", "text": "q0", "origin": "original", "focus": "original_intent"},
                {"query_id": "Q1", "text": "q1", "origin": "generated", "focus": "paraphrase"}]},
            "trace": {"union_child_count": len(hits)},
        }

    def test_end_to_end_returns_parents(self):
        res = hr.parent_retrieval("Điều 7?", self.config, self.hcfg,
                                  chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                                  child_result=self._child_result())
        self.assertTrue(res["parents"])
        for p in res["parents"]:
            self.assertIn(p["parent_id"], self.parents_by_id)
            self.assertIn("scoring_child_ids", p)
            self.assertIn("supporting_child_ids", p)

    def test_expansion_factor_greater_than_one(self):
        res = hr.parent_retrieval("Điều 7?", self.config, self.hcfg,
                                  chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                                  child_result=self._child_result())
        tr = res["trace"]
        self.assertGreater(tr["parent_chars"], 0)
        self.assertGreaterEqual(tr["context_expansion_factor"], 1.0,
                                "parent phải rộng hơn hoặc bằng child")

    def test_trace_has_all_required_keys(self):
        res = hr.parent_retrieval("Điều 7?", self.config, self.hcfg,
                                  chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                                  child_result=self._child_result())
        tr = res["trace"]
        for key in ("input_child_hit_count", "unique_parent_count", "children_per_parent",
                    "child_to_parent", "parent_score_components", "dropped_by_candidate_limit",
                    "dropped_by_context_budget", "child_chars", "parent_chars",
                    "context_expansion_factor", "total_context_chars",
                    "ambiguous_parent_count", "warning_count", "latency_ms"):
            self.assertIn(key, tr)
        self.assertIn("aggregation", tr["latency_ms"])

    def test_child_to_parent_table_covers_all_hits(self):
        cr = self._child_result()
        res = hr.parent_retrieval("Điều 7?", self.config, self.hcfg,
                                  chunks_dir=FIXTURES, hierarchy_dir=self.hdir, child_result=cr)
        self.assertEqual(set(res["trace"]["child_to_parent"]),
                         {h["child_id"] for h in cr["child_hits"]})

    def test_invalid_mode_rejected(self):
        with self.assertRaises(hr.HierarchyError):
            hr.parent_retrieval("q", self.config, self.hcfg, mode="multi_flat",
                                chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                                child_result=self._child_result())

    def test_status_propagates_from_child_stage(self):
        res = hr.parent_retrieval("q", self.config, self.hcfg,
                                  chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                                  child_result=self._child_result(status="multi_query_partial"))
        self.assertEqual(res["status"], "multi_query_partial")

    def test_single_parent_mode_no_variants(self):
        """single_parent chỉ dùng Q0 -> không gọi generator."""
        calls = []

        class FakeHybrid:
            def __init__(self, outer):
                self.outer = outer

            def __call__(self, question, config, strategy, bm25_index=None, chunks_dir=None,
                         persist_path=None, client_factory=None):
                cids = self.outer.child_ids[:3]
                return {"candidates": [{
                    "chunk_id": cid, "text": self.outer.children[cid]["text"],
                    "source": self.outer.children[cid]["source"],
                    "page_start": self.outer.children[cid]["page_start"],
                    "page_end": self.outer.children[cid]["page_end"],
                    "bm25_rank": i, "bm25_score": 1.0, "semantic_rank": i,
                    "semantic_distance": 0.1, "rrf_score": 1.0 / (60 + i),
                    "fused_rank": i, "matched_by": ["bm25"],
                } for i, cid in enumerate(cids, start=1)], "trace": {}}

        res = hr.parent_retrieval(
            "Điều 7 quy định gì?", self.config, self.hcfg, mode="single_parent",
            chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
            query_generator_fn=lambda *a: calls.append(1),
            hybrid_fn=FakeHybrid(self),
        )
        self.assertEqual(calls, [], "single_parent KHÔNG sinh query variant")
        self.assertEqual(len(res["query_set"]["queries"]), 1)
        self.assertTrue(res["parents"])

    def test_no_reranker_or_generation_called(self):
        calls = []
        orig_r, orig_g, orig_load = (ar.rerank_candidates, ar.generate_grounded_answer,
                                     ar.load_reranker)
        try:
            ar.rerank_candidates = lambda *a, **kw: calls.append("rerank")
            ar.generate_grounded_answer = lambda *a, **kw: calls.append("generate")
            ar.load_reranker = lambda *a, **kw: calls.append("load_reranker")
            hr.parent_retrieval("q", self.config, self.hcfg,
                                chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                                child_result=self._child_result())
            self.assertEqual(calls, [])
        finally:
            ar.rerank_candidates, ar.generate_grounded_answer, ar.load_reranker = (
                orig_r, orig_g, orig_load)

    def test_children_per_parent_counts(self):
        cr = self._child_result()
        res = hr.parent_retrieval("q", self.config, self.hcfg,
                                  chunks_dir=FIXTURES, hierarchy_dir=self.hdir, child_result=cr)
        total = sum(res["trace"]["children_per_parent"].values())
        self.assertEqual(total, len(cr["child_hits"]))

    def test_no_duplicate_child_text_across_parents(self):
        """Invariant hierarchy: một child chỉ thuộc đúng một parent."""
        seen = {}
        for pid, p in self.parents_by_id.items():
            for cid in p["child_ids"]:
                self.assertNotIn(cid, seen,
                                 f"child {cid} xuất hiện ở cả {seen.get(cid)} và {pid}")
                seen[cid] = pid


if __name__ == "__main__":
    unittest.main()
