"""tests/test_crossquery.py — Test per-query retrieval và Cross-query RRF (Bước 05).

Offline hoàn toàn: hybrid retriever và query generator đều được tiêm giả lập —
không mạng, không Chroma thật, không model.
"""

from __future__ import annotations

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


def cand(cid, fused_rank, text=None, source="s.pdf", p1=1, p2=1, bm25_rank=None, sem_rank=None):
    """Candidate giả lập giống output hybrid_search của Buổi 08."""
    return {
        "chunk_id": cid,
        "text": text if text is not None else f"nội dung {cid}",
        "source": source,
        "page_start": p1,
        "page_end": p2,
        "bm25_rank": bm25_rank,
        "bm25_score": 1.0 if bm25_rank else None,
        "semantic_rank": sem_rank,
        "semantic_distance": 0.2 if sem_rank else None,
        "rrf_score": 1.0 / (60 + fused_rank),
        "fused_rank": fused_rank,
        "matched_by": ["bm25"] if bm25_rank else ["semantic"],
    }


class FakeHybrid:
    """hybrid_search giả lập: trả kết quả định sẵn theo TEXT của query."""

    def __init__(self, by_query=None, raises_for=None):
        self.by_query = by_query or {}
        self.raises_for = raises_for or {}
        self.calls = []

    def __call__(self, question, config, strategy, bm25_index=None, chunks_dir=None,
                 persist_path=None, client_factory=None):
        self.calls.append(question)
        if question in self.raises_for:
            raise self.raises_for[question]
        return {"candidates": self.by_query.get(question, []), "trace": {}}


def query_set(*texts_and_origins):
    """Tạo query set thủ công: [('text','original'), ('text','generated'), ...]"""
    queries = []
    for i, (text, origin) in enumerate(texts_and_origins):
        queries.append({
            "query_id": f"Q{i}",
            "text": text,
            "origin": origin,
            "focus": "original_intent" if origin == "original" else "paraphrase",
        })
    return {
        "original_question": texts_and_origins[0][0],
        "queries": queries,
        "model": "fake-model",
        "generation_latency_ms": 0.0,
        "cache_hit": False,
        "dropped_duplicate_count": 0,
        "dropped_invalid_count": 0,
        "warnings": [],
        "status": "ready",
    }


class CrossQueryBase(unittest.TestCase):
    def setUp(self):
        hr.clear_query_cache()
        self.work = Path(tempfile.mkdtemp())
        env = write_env(self.work / ".env")
        self.config = ar.load_advanced_config(env)
        self.hcfg = hr.load_hierarchy_config(env)

    def tearDown(self):
        hr.clear_query_cache()
        shutil.rmtree(self.work, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. Công thức MQ-RRF
# ---------------------------------------------------------------------------


class FormulaTests(CrossQueryBase):
    def test_formula_hand_computed(self):
        """
        Q0 (weight 1.5) rank 2, Q1 (weight 1.0) rank 1, K=60:
          1.5/(60+2) + 1.0/(60+1) = 0.024193548... + 0.016393442... = 0.040586990...
        """
        qs = query_set(("câu gốc", "original"), ("biến thể", "generated"))
        per_query = {"Q0": [cand("c1", 2)], "Q1": [cand("c1", 1)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        expected = 1.5 / 62 + 1.0 / 61
        self.assertAlmostEqual(fused[0]["multi_query_rrf_score"], expected, places=12)
        self.assertAlmostEqual(expected, 0.04058699, places=7)

    def test_original_weight_higher_than_variant(self):
        """Cùng rank 1: child do Q0 tìm phải thắng child do Q1 tìm."""
        qs = query_set(("câu gốc", "original"), ("biến thể", "generated"))
        per_query = {"Q0": [cand("by_q0", 1)], "Q1": [cand("by_q1", 1)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        self.assertEqual(fused[0]["child_id"], "by_q0")
        self.assertAlmostEqual(fused[0]["multi_query_rrf_score"], 1.5 / 61, places=12)
        self.assertAlmostEqual(fused[1]["multi_query_rrf_score"], 1.0 / 61, places=12)

    def test_only_rank_used_not_raw_scores(self):
        """Inner RRF score/BM25 score khác nhau nhưng cùng rank -> cùng MQ-RRF."""
        qs = query_set(("q", "original"))
        a = cand("c1", 1)
        a["rrf_score"], a["bm25_score"] = 999.0, 999.0
        b = cand("c2", 1)
        b["rrf_score"], b["bm25_score"] = 0.0001, 0.0001
        f1 = hr.cross_query_rrf({"Q0": [a]}, qs, self.hcfg)
        f2 = hr.cross_query_rrf({"Q0": [b]}, qs, self.hcfg)
        self.assertAlmostEqual(f1[0]["multi_query_rrf_score"], f2[0]["multi_query_rrf_score"], places=12)

    def test_missing_query_contributes_nothing(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        per_query = {"Q0": [cand("c1", 1)], "Q1": []}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        self.assertAlmostEqual(fused[0]["multi_query_rrf_score"], 1.5 / 61, places=12)
        self.assertEqual(fused[0]["support_query_count"], 1)

    def test_three_queries_accumulate(self):
        qs = query_set(("q0", "original"), ("q1", "generated"), ("q2", "generated"))
        per_query = {"Q0": [cand("c1", 3)], "Q1": [cand("c1", 2)], "Q2": [cand("c1", 5)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        expected = 1.5 / 63 + 1.0 / 62 + 1.0 / 65
        self.assertAlmostEqual(fused[0]["multi_query_rrf_score"], expected, places=12)

    def test_custom_rrf_k(self):
        env = write_env(self.work / "k.env", MULTI_QUERY_RRF_K="10")
        hcfg = hr.load_hierarchy_config(env)
        qs = query_set(("q0", "original"))
        fused = hr.cross_query_rrf({"Q0": [cand("c1", 1)]}, qs, hcfg)
        self.assertAlmostEqual(fused[0]["multi_query_rrf_score"], 1.5 / 11, places=12)


# ---------------------------------------------------------------------------
# 2. Merge contract
# ---------------------------------------------------------------------------


class MergeTests(CrossQueryBase):
    def test_union_no_duplicate(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        per_query = {
            "Q0": [cand("c1", 1), cand("c2", 2)],
            "Q1": [cand("c1", 1), cand("c3", 2)],
        }
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        ids = [e["child_id"] for e in fused]
        self.assertEqual(sorted(ids), ["c1", "c2", "c3"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_support_query_ids_in_order(self):
        qs = query_set(("q0", "original"), ("q1", "generated"), ("q2", "generated"))
        per_query = {"Q2": [cand("c1", 1)], "Q0": [cand("c1", 2)], "Q1": [cand("c1", 3)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        self.assertEqual(fused[0]["support_query_ids"], ["Q0", "Q1", "Q2"],
                         "phải theo thứ tự Q0, Q1, Q2 bất kể thứ tự dict")

    def test_per_query_ranks_recorded(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        per_query = {"Q0": [cand("c1", 4)], "Q1": [cand("c1", 7)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        self.assertEqual(fused[0]["per_query_ranks"], {"Q0": 4, "Q1": 7})
        self.assertEqual(fused[0]["best_query_rank"], 4)

    def test_candidate_in_single_query_kept(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        per_query = {"Q0": [cand("only_q0", 1)], "Q1": [cand("only_q1", 1)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        self.assertEqual(len(fused), 2)
        for e in fused:
            self.assertEqual(e["support_query_count"], 1)

    def test_metadata_mismatch_fails(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        for field, v0, v1 in (("text", "A", "B"), ("source", "a.pdf", "b.pdf")):
            with self.subTest(field=field):
                a = cand("c1", 1, **{field: v0} if field == "text" else {})
                b = cand("c1", 1, **{field: v1} if field == "text" else {})
                if field == "source":
                    a = cand("c1", 1, source=v0)
                    b = cand("c1", 1, source=v1)
                with self.assertRaises(rag.DataError):
                    hr.cross_query_rrf({"Q0": [a], "Q1": [b]}, qs, self.hcfg)

    def test_page_mismatch_fails(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        with self.assertRaises(rag.DataError):
            hr.cross_query_rrf(
                {"Q0": [cand("c1", 1, p1=1, p2=2)], "Q1": [cand("c1", 1, p1=5, p2=6)]},
                qs, self.hcfg,
            )

    def test_per_query_trace_kept(self):
        qs = query_set(("q0", "original"))
        c = cand("c1", 1, bm25_rank=3, sem_rank=5)
        fused = hr.cross_query_rrf({"Q0": [c]}, qs, self.hcfg)
        tr = fused[0]["per_query_trace"]["Q0"]
        self.assertEqual(tr["bm25_rank"], 3)
        self.assertEqual(tr["semantic_rank"], 5)
        self.assertEqual(tr["inner_rrf_rank"], 1)


# ---------------------------------------------------------------------------
# 3. Sắp xếp
# ---------------------------------------------------------------------------


class OrderingTests(CrossQueryBase):
    def test_rank_sequential_from_one(self):
        qs = query_set(("q0", "original"))
        per_query = {"Q0": [cand(f"c{i}", i) for i in range(1, 6)]}
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        self.assertEqual([e["multi_query_rank"] for e in fused], [1, 2, 3, 4, 5])

    def test_score_descending(self):
        qs = query_set(("q0", "original"), ("q1", "generated"))
        per_query = {
            "Q0": [cand("a", 1), cand("b", 5)],
            "Q1": [cand("b", 1), cand("c", 3)],
        }
        fused = hr.cross_query_rrf(per_query, qs, self.hcfg)
        scores = [e["multi_query_rrf_score"] for e in fused]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_tie_break_deterministic(self):
        """Cùng score -> support count -> best rank -> child_id."""
        qs = query_set(("q0", "original"))
        per_query = {"Q0": [cand("zz", 1), cand("aa", 1), cand("mm", 1)]}
        f1 = [e["child_id"] for e in hr.cross_query_rrf(per_query, qs, self.hcfg)]
        f2 = [e["child_id"] for e in hr.cross_query_rrf(per_query, qs, self.hcfg)]
        self.assertEqual(f1, f2)
        self.assertEqual(f1, ["aa", "mm", "zz"])

    def test_support_count_breaks_tie_before_rank(self):
        """Hai child cùng score: child được nhiều query hỗ trợ hơn xếp trước."""
        qs = query_set(("q0", "original"), ("q1", "generated"))
        # weight bằng nhau; multi: 2 × 1/(60+180) = 1/120 == single: 1/(60+60) = 1/120
        env = write_env(self.work / "eq.env", MULTI_QUERY_ORIGINAL_WEIGHT="1.0")
        hcfg = hr.load_hierarchy_config(env)
        per_query = {
            "Q0": [cand("multi", 180), cand("single", 60)],
            "Q1": [cand("multi", 180)],
        }
        fused = hr.cross_query_rrf(per_query, qs, hcfg)
        by_id = {e["child_id"]: e for e in fused}
        self.assertAlmostEqual(by_id["multi"]["multi_query_rrf_score"],
                               by_id["single"]["multi_query_rrf_score"], places=12)
        self.assertLess(by_id["multi"]["multi_query_rank"], by_id["single"]["multi_query_rank"])


# ---------------------------------------------------------------------------
# 4. Pipeline + failure contract
# ---------------------------------------------------------------------------


class PipelineTests(CrossQueryBase):
    def _run(self, hybrid, use_variants=True, gen=None, question="Điều 7 quy định gì?"):
        return hr.multi_query_child_retrieval(
            question, self.config, self.hcfg,
            use_variants=use_variants,
            query_generator_fn=gen or (lambda q, c, h: {"queries": [
                {"text": "biến thể một", "focus": "paraphrase"},
                {"text": "biến thể hai", "focus": "exact_legal_terms"},
            ]}),
            hybrid_fn=hybrid,
            chunks_dir=Path(__file__).resolve().parent / "fixtures",
        )

    def test_each_query_calls_hybrid_exactly_once(self):
        hybrid = FakeHybrid(by_query={
            "Điều 7 quy định gì?": [cand("c1", 1)],
            "biến thể một": [cand("c2", 1)],
            "biến thể hai": [cand("c3", 1)],
        })
        res = self._run(hybrid)
        self.assertEqual(len(hybrid.calls), 3)
        self.assertEqual(len(set(hybrid.calls)), 3, "mỗi query gọi đúng 1 lần")

    def test_single_mode_only_q0_no_generation(self):
        hybrid = FakeHybrid(by_query={"Điều 7 quy định gì?": [cand("c1", 1)]})
        calls = []
        res = self._run(hybrid, use_variants=False, gen=lambda *a: calls.append(1))
        self.assertEqual(len(res["query_set"]["queries"]), 1)
        self.assertEqual(calls, [], "single mode KHÔNG gọi sinh query")
        self.assertEqual(res["trace"]["generation_call_count"], 0)
        self.assertEqual(len(hybrid.calls), 1)

    def test_q0_failure_raises(self):
        hybrid = FakeHybrid(raises_for={"Điều 7 quy định gì?": RuntimeError("Q0 hỏng")})
        with self.assertRaises(RuntimeError):
            self._run(hybrid)

    def test_variant_failure_gives_partial_status(self):
        hybrid = FakeHybrid(
            by_query={"Điều 7 quy định gì?": [cand("c1", 1)], "biến thể hai": [cand("c3", 1)]},
            raises_for={"biến thể một": RuntimeError("mạng lỗi")},
        )
        res = self._run(hybrid)
        self.assertEqual(res["status"], "multi_query_partial")
        self.assertIn("Q1", res["trace"]["failed_queries"])
        self.assertEqual(res["trace"]["query_count_failed"], 1)
        self.assertTrue(any("Q1" in w for w in res["warnings"]))

    def test_failed_query_not_counted_as_zero_result(self):
        hybrid = FakeHybrid(
            by_query={"Điều 7 quy định gì?": [cand("c1", 1)]},
            raises_for={"biến thể một": RuntimeError("lỗi"), "biến thể hai": RuntimeError("lỗi")},
        )
        res = self._run(hybrid)
        self.assertNotIn("Q1", res["trace"]["result_count_per_query"],
                         "query lỗi KHÔNG được ghi là 0 kết quả")
        self.assertEqual(res["trace"]["query_count_executed"], 1)

    def test_query_generation_unavailable_propagates(self):
        def broken_gen(q, c, h):
            raise hr.QueryGenerationError("API sập")

        hybrid = FakeHybrid(by_query={"Điều 7 quy định gì?": [cand("c1", 1)]})
        res = self._run(hybrid, gen=broken_gen)
        self.assertEqual(res["status"], "query_generation_unavailable")
        self.assertEqual(len(hybrid.calls), 1, "chỉ còn Q0 để chạy")

    def test_trace_has_all_keys(self):
        hybrid = FakeHybrid(by_query={"Điều 7 quy định gì?": [cand("c1", 1)]})
        tr = self._run(hybrid)["trace"]
        for key in ("query_count_requested", "query_count_valid", "query_count_executed",
                    "query_count_failed", "result_count_per_query", "union_child_count",
                    "overlap_distribution", "generation_call_count", "embedding_call_count",
                    "latency_ms"):
            self.assertIn(key, tr)
        for key in ("query_expansion", "per_query_retrieval", "fusion", "total"):
            self.assertIn(key, tr["latency_ms"])

    def test_overlap_distribution_correct(self):
        hybrid = FakeHybrid(by_query={
            "Điều 7 quy định gì?": [cand("both", 1), cand("only_q0", 2)],
            "biến thể một": [cand("both", 1)],
            "biến thể hai": [],
        })
        res = self._run(hybrid)
        self.assertEqual(res["trace"]["overlap_distribution"], {1: 1, 2: 1})

    def test_no_rerank_or_generation_called(self):
        """Bước 05 tuyệt đối không chạm reranker hay answer generation."""
        calls = []
        orig_rerank, orig_gen = ar.rerank_candidates, ar.generate_grounded_answer
        try:
            ar.rerank_candidates = lambda *a, **kw: calls.append("rerank")
            ar.generate_grounded_answer = lambda *a, **kw: calls.append("generate")
            hybrid = FakeHybrid(by_query={"Điều 7 quy định gì?": [cand("c1", 1)]})
            self._run(hybrid)
            self.assertEqual(calls, [])
        finally:
            ar.rerank_candidates, ar.generate_grounded_answer = orig_rerank, orig_gen

    def test_embedding_call_count_tracks_executed_queries(self):
        hybrid = FakeHybrid(by_query={
            "Điều 7 quy định gì?": [cand("c1", 1)],
            "biến thể một": [cand("c2", 1)],
            "biến thể hai": [cand("c3", 1)],
        })
        res = self._run(hybrid)
        self.assertEqual(res["trace"]["embedding_call_count"], 3)
        self.assertEqual(res["trace"]["generation_call_count"], 1,
                         "sinh query = 1 generation call, tách riêng embedding")


if __name__ == "__main__":
    unittest.main()
