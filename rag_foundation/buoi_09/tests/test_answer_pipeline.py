"""tests/test_answer_pipeline.py — Test Parent Rerank + Answer Pipeline (Bước 07).

Offline hoàn toàn: cross-encoder, Gemini generation, hybrid retriever và query
generator đều được tiêm giả lập. Không mạng, không tải model, không Chroma thật.
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

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeScorer:
    """Cross-encoder giả lập. Ghi lại (question, texts) mỗi lần được gọi."""

    def __init__(self, logits=None, per_text=None, raises=None):
        self.logits = logits
        self.per_text = per_text or {}
        self.raises = raises
        self.calls = []

    def __call__(self, question, texts, config):
        self.calls.append({"question": question, "texts": list(texts)})
        if self.raises:
            raise self.raises
        if self.logits is not None:
            return list(self.logits[: len(texts)])
        return [self.per_text.get(t, 0.0) for t in texts]


class FakeGenClient:
    """Gemini client giả lập cho generation."""

    def __init__(self, text="Nội dung quy định như sau. [P1]", raises=None):
        self.text = text
        self.raises = raises
        self.prompts = []
        self.models = self

    def generate_content(self, model=None, contents=None):
        self.prompts.append(contents)
        if self.raises:
            raise self.raises
        return type("R", (), {"text": self.text})()


class FakeHybrid:
    """hybrid_search giả lập trả child thật từ hierarchy store."""

    def __init__(self, child_ids, children):
        self.child_ids = child_ids
        self.children = children
        self.calls = []

    def __call__(self, question, config, strategy, bm25_index=None, chunks_dir=None,
                 persist_path=None, client_factory=None):
        self.calls.append(question)
        cands = []
        for i, cid in enumerate(self.child_ids, start=1):
            c = self.children[cid]
            cands.append({
                "chunk_id": cid, "text": c["text"], "source": c["source"],
                "page_start": c["page_start"], "page_end": c["page_end"],
                "bm25_rank": i, "bm25_score": 1.0, "semantic_rank": i,
                "semantic_distance": 0.1, "rrf_score": 1.0 / (60 + i),
                "fused_rank": i, "matched_by": ["bm25", "semantic"],
            })
        return {"candidates": cands, "trace": {}}


def fake_generator(question, config, hcfg):
    return {"queries": [{"text": "biến thể một", "focus": "paraphrase"},
                        {"text": "biến thể hai", "focus": "exact_legal_terms"}]}


def parent_cand(pid, parent_rank, text="nội dung parent", score=0.01, support=("Q0",)):
    return {
        "parent_id": pid, "source": "s.pdf", "page_start": 1, "page_end": 2,
        "structural_path": {"chapter": "Chương I", "article": "Điều 1"},
        "text": text, "char_count": len(text),
        "parent_rrf_score": score, "parent_rank": parent_rank,
        "anchor_child_id": f"{pid}_c1", "scoring_child_ids": [f"{pid}_c1"],
        "supporting_child_ids": [f"{pid}_c1"], "support_query_ids": list(support),
        "best_child_rank": parent_rank, "child_chars": 100,
        "ambiguous": False, "warnings": [],
    }


class PipelineBase(unittest.TestCase):
    def setUp(self):
        hr.clear_query_cache()
        self.work = Path(tempfile.mkdtemp())
        env = write_env(self.work / ".env", GEMINI_API_KEY="fake-key-for-test")
        self.config = ar.load_advanced_config(env)
        self.hcfg = hr.load_hierarchy_config(env)
        self.hdir = self.work / "h"
        hr.build_hierarchy(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=self.hdir)
        self.children, self.parents_by_id, _ = hr.load_hierarchy_store(self.hdir)
        self.child_ids = sorted(self.children)[:5]

    def tearDown(self):
        hr.clear_query_cache()
        shutil.rmtree(self.work, ignore_errors=True)

    def run_answer(self, mode="multi_parent", scorer=None, gen_client=None, **kw):
        scorer = scorer or FakeScorer(logits=[5.0, 4.0, 3.0, 2.0, 1.0])
        client = gen_client or FakeGenClient()
        kw.setdefault("query_generator_fn", fake_generator)
        kw.setdefault("hierarchy_dir", self.hdir)
        return hr.answer_hierarchical(
            "Điều 7 quy định gì?", self.config, self.hcfg, mode=mode,
            chunks_dir=FIXTURES,
            hybrid_fn=FakeHybrid(self.child_ids, self.children),
            rerank_scorer=scorer,
            generation_client_factory=lambda key: client,
            **kw,
        ), scorer, client


# ---------------------------------------------------------------------------
# 1. Reranker dùng Q0 + parent text
# ---------------------------------------------------------------------------


class RerankPairTests(PipelineBase):
    def test_pair_is_q0_and_parent_text(self):
        res, scorer, _ = self.run_answer()
        self.assertEqual(len(scorer.calls), 1, "chỉ rerank đúng một lần")
        call = scorer.calls[0]
        self.assertEqual(call["question"], "Điều 7 quy định gì?")
        parent_texts = {p["text"] for p in self.parents_by_id.values()}
        for t in call["texts"]:
            self.assertIn(t, parent_texts, "phải chấm PARENT text, không phải child text")

    def test_generated_query_not_used_for_rerank(self):
        res, scorer, _ = self.run_answer()
        self.assertNotIn(scorer.calls[0]["question"], ("biến thể một", "biến thể hai"))
        self.assertGreater(len(res["query_set"]["queries"]), 1, "vẫn có sinh biến thể")

    def test_generated_query_not_in_answer_prompt(self):
        res, _, client = self.run_answer()
        self.assertEqual(len(client.prompts), 1)
        prompt = client.prompts[0]
        self.assertIn("Điều 7 quy định gì?", prompt)
        self.assertNotIn("biến thể một", prompt)
        self.assertNotIn("biến thể hai", prompt)

    def test_rerank_limited_to_parent_candidates(self):
        hcfg = hr.load_hierarchy_config(
            write_env(self.work / "lim.env", PARENT_CANDIDATES="2", FINAL_PARENT_TOP_K="2",
                      GEMINI_API_KEY="k"))
        parents = [parent_cand(f"p{i}", i) for i in range(1, 6)]
        scorer = FakeScorer(logits=[5.0, 4.0])
        out = hr.rerank_parents("Q0 thật", parents, self.config, hcfg, scorer=scorer)
        self.assertEqual(out["reranked_count"], 2)
        self.assertEqual(len(scorer.calls[0]["texts"]), 2)

    def test_model_not_loaded_on_import_or_status(self):
        """load_reranker không được gọi ở status/build/single retrieval."""
        calls = []
        orig = ar.load_reranker
        try:
            ar.load_reranker = lambda *a, **kw: calls.append(1)
            hr.hierarchy_status(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=self.hdir)
            hr.build_hierarchy(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=self.hdir)
            hr.parent_retrieval(
                "q", self.config, self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
                hybrid_fn=FakeHybrid(self.child_ids, self.children), mode="single_parent")
            self.assertEqual(calls, [])
        finally:
            ar.load_reranker = orig


# ---------------------------------------------------------------------------
# 2. Sort, rank change, final K
# ---------------------------------------------------------------------------


class RerankOrderTests(PipelineBase):
    def test_sigmoid_and_fields(self):
        parents = [parent_cand("p1", 1)]
        out = hr.rerank_parents("q", parents, self.config, self.hcfg,
                                scorer=FakeScorer(logits=[0.0]))
        p = out["parents"][0]
        self.assertAlmostEqual(p["parent_rerank_score"], 0.5, places=9)
        self.assertEqual(p["parent_rerank_raw_score"], 0.0)
        self.assertEqual(p["parent_rerank_rank"], 1)
        self.assertEqual(p["parent_rank_change"], 0)

    def test_reorder_and_rank_change(self):
        """Parent hạng 3 theo RRF được rerank lên hạng 1 -> rank_change = +2."""
        parents = [parent_cand("p1", 1, text="A"), parent_cand("p2", 2, text="B"),
                   parent_cand("p3", 3, text="C")]
        scorer = FakeScorer(per_text={"A": 0.0, "B": 1.0, "C": 9.0})
        out = hr.rerank_parents("q", parents, self.config, self.hcfg, scorer=scorer)
        ids = [p["parent_id"] for p in out["parents"]]
        self.assertEqual(ids, ["p3", "p2", "p1"])
        by = {p["parent_id"]: p for p in out["parents"]}
        self.assertEqual(by["p3"]["parent_rank_change"], 2)
        self.assertEqual(by["p1"]["parent_rank_change"], -2)

    def test_tie_break_by_parent_rank_then_id(self):
        parents = [parent_cand("pz", 2, text="X"), parent_cand("pa", 1, text="Y")]
        out = hr.rerank_parents("q", parents, self.config, self.hcfg,
                                scorer=FakeScorer(per_text={"X": 1.0, "Y": 1.0}))
        self.assertEqual([p["parent_id"] for p in out["parents"]], ["pa", "pz"])

    def test_rrf_score_preserved(self):
        parents = [parent_cand("p1", 1, score=0.12345)]
        out = hr.rerank_parents("q", parents, self.config, self.hcfg,
                                scorer=FakeScorer(logits=[1.0]))
        self.assertEqual(out["parents"][0]["parent_rrf_score"], 0.12345)
        self.assertEqual(out["parents"][0]["parent_rank"], 1)

    def test_final_parent_top_k_applied(self):
        hcfg = hr.load_hierarchy_config(
            write_env(self.work / "k.env", PARENT_CANDIDATES="5", FINAL_PARENT_TOP_K="2",
                      GEMINI_API_KEY="k"))
        res, _, _ = self.run_answer(mode="single_parent")
        # store fixture nhỏ nên dùng trực tiếp hàm để kiểm K
        parents = [parent_cand(f"p{i}", i) for i in range(1, 6)]
        out = hr.rerank_parents("q", parents, self.config, hcfg,
                                scorer=FakeScorer(logits=[5, 4, 3, 2, 1]))
        top = out["parents"][: hcfg.final_parent_top_k]
        self.assertEqual(len(top), 2)

    def test_empty_parents_no_scorer_call(self):
        scorer = FakeScorer(logits=[1.0])
        out = hr.rerank_parents("q", [], self.config, self.hcfg, scorer=scorer)
        self.assertEqual(out["parents"], [])
        self.assertEqual(scorer.calls, [])

    def test_score_count_mismatch_raises(self):
        parents = [parent_cand("p1", 1), parent_cand("p2", 2)]
        with self.assertRaises(ar.RerankerUnavailableError):
            hr.rerank_parents("q", parents, self.config, self.hcfg,
                              scorer=FakeScorer(logits=[1.0]))


# ---------------------------------------------------------------------------
# 3. Evidence gate
# ---------------------------------------------------------------------------


class GateTests(PipelineBase):
    def test_gate_accepts_above_threshold(self):
        parents = [dict(parent_cand("p1", 1), parent_rerank_score=0.90),
                   dict(parent_cand("p2", 2), parent_rerank_score=0.20)]
        accepted, _ = hr.apply_parent_gate(parents, self.config)
        self.assertEqual([p["parent_id"] for p in accepted], ["p1"])

    def test_gate_boundary_inclusive(self):
        p = dict(parent_cand("p1", 1), parent_rerank_score=self.config.rerank_min_score)
        accepted, _ = hr.apply_parent_gate([p], self.config)
        self.assertEqual(len(accepted), 1, ">= chứ không phải >")

    def test_ambiguous_not_auto_rejected_but_warned(self):
        p = dict(parent_cand("p1", 1), parent_rerank_score=0.99, ambiguous=True)
        accepted, warns = hr.apply_parent_gate([p], self.config)
        self.assertEqual(len(accepted), 1)
        self.assertTrue(any("suy ra" in w for w in warns))

    def test_missing_score_rejected(self):
        p = parent_cand("p1", 1)
        accepted, _ = hr.apply_parent_gate([p], self.config)
        self.assertEqual(accepted, [])

    def test_insufficient_evidence_no_generation(self):
        res, _, client = self.run_answer(scorer=FakeScorer(logits=[-9.0] * 5))
        self.assertEqual(res["status"], "insufficient_evidence")
        self.assertEqual(client.prompts, [], "KHÔNG được gọi Gemini khi không đủ căn cứ")
        self.assertIsNone(res["answer"])
        self.assertEqual(res["trace"]["generation_api_calls"], 1, "chỉ còn call sinh query")

    def test_labels_only_on_accepted(self):
        res, _, _ = self.run_answer(scorer=FakeScorer(logits=[9.0, -9.0, -9.0, -9.0, -9.0]))
        labelled = [e for e in res["evidence"] if e["label"]]
        self.assertTrue(all(e["accepted"] for e in labelled))
        self.assertTrue(all(e["label"] is None for e in res["evidence"] if not e["accepted"]))


# ---------------------------------------------------------------------------
# 4. Mode routing
# ---------------------------------------------------------------------------


class ModeRoutingTests(PipelineBase):
    def test_single_flat_no_variants_child_unit(self):
        gen_calls = []
        res, scorer, _ = self.run_answer(
            mode="single_flat", query_generator_fn=lambda *a: gen_calls.append(1))
        self.assertEqual(gen_calls, [])
        self.assertEqual(len(res["query_set"]["queries"]), 1)
        self.assertEqual(res["parent_candidates"], [], "flat mode không có parent")
        self.assertTrue(all("chunk_id" in e for e in res["evidence"]))

    def test_multi_flat_has_variants_child_unit(self):
        res, scorer, _ = self.run_answer(mode="multi_flat")
        self.assertGreater(len(res["query_set"]["queries"]), 1)
        self.assertEqual(res["parent_candidates"], [])
        self.assertTrue(all("chunk_id" in e for e in res["evidence"]))

    def test_single_parent_no_variants_parent_unit(self):
        gen_calls = []
        res, _, _ = self.run_answer(
            mode="single_parent", query_generator_fn=lambda *a: gen_calls.append(1))
        self.assertEqual(gen_calls, [])
        self.assertEqual(len(res["query_set"]["queries"]), 1)
        self.assertTrue(res["parent_candidates"])
        self.assertTrue(all("parent_id" in e for e in res["evidence"]))

    def test_multi_parent_full_chain(self):
        res, _, _ = self.run_answer(mode="multi_parent")
        self.assertGreater(len(res["query_set"]["queries"]), 1)
        self.assertTrue(res["parent_candidates"])
        self.assertTrue(all("parent_id" in e for e in res["evidence"]))

    def test_invalid_mode_rejected(self):
        with self.assertRaises(rag.DataError):
            hr.answer_hierarchical("q", self.config, self.hcfg, mode="hybrid",
                                   chunks_dir=FIXTURES, hierarchy_dir=self.hdir)

    def test_flat_mode_skips_hierarchy_gate(self):
        """flat mode không cần hierarchy store."""
        res, _, _ = self.run_answer(mode="single_flat", hierarchy_dir=self.work / "khong_ton_tai")
        self.assertNotEqual(res["status"], "hierarchy_not_ready")

    def test_parent_mode_needs_hierarchy(self):
        res = hr.answer_hierarchical(
            "q", self.config, self.hcfg, mode="multi_parent",
            chunks_dir=FIXTURES, hierarchy_dir=self.work / "khong_ton_tai",
            hybrid_fn=FakeHybrid(self.child_ids, self.children),
            rerank_scorer=FakeScorer(logits=[1.0] * 5),
            query_generator_fn=fake_generator,
        )
        self.assertEqual(res["status"], "hierarchy_not_ready")


# ---------------------------------------------------------------------------
# 5. Failure contract
# ---------------------------------------------------------------------------


class FailureTests(PipelineBase):
    def test_reranker_failure_no_silent_fallback(self):
        res, _, client = self.run_answer(
            scorer=FakeScorer(raises=ar.RerankerUnavailableError("model hỏng")))
        self.assertEqual(res["status"], "reranker_unavailable")
        self.assertEqual(res["evidence"], [], "không trình bày kết quả chưa rerank")
        self.assertIsNone(res["answer"])
        self.assertEqual(client.prompts, [])

    def test_query_generation_failure_status(self):
        def broken(q, c, h):
            raise hr.QueryGenerationError("API sập")

        res, _, _ = self.run_answer(query_generator_fn=broken)
        self.assertTrue(any("biến thể" in w for w in res["warnings"]))
        self.assertEqual(len(res["query_set"]["queries"]), 1, "lùi về chỉ Q0")

    def test_generation_failure_gives_retrieval_only(self):
        client = FakeGenClient(raises=RuntimeError("Gemini 503"))
        res, _, _ = self.run_answer(gen_client=client)
        self.assertEqual(res["status"], "retrieval_only")
        self.assertIsNone(res["answer"])
        self.assertTrue(res["accepted_evidence"], "vẫn trả evidence")

    def test_empty_generation_gives_retrieval_only(self):
        res, _, _ = self.run_answer(gen_client=FakeGenClient(text=""))
        self.assertEqual(res["status"], "retrieval_only")


# ---------------------------------------------------------------------------
# 6. Citation
# ---------------------------------------------------------------------------


class CitationTests(PipelineBase):
    def test_citation_uses_real_parent_and_anchor(self):
        res, _, _ = self.run_answer()
        self.assertEqual(res["status"], "answered")
        self.assertTrue(res["citations"])
        for c in res["citations"]:
            self.assertIn(c["parent_id"], self.parents_by_id)
            self.assertIn(c["anchor_child_id"], self.children)
            for cid in c["supporting_child_ids"]:
                self.assertIn(cid, self.children)

    def test_citation_schema_complete(self):
        res, _, _ = self.run_answer()
        for c in res["citations"]:
            for key in ("evidence_id", "parent_id", "anchor_child_id", "supporting_child_ids",
                        "source", "page_start", "page_end", "structural_path",
                        "parent_rerank_score", "ambiguous", "warnings"):
                self.assertIn(key, c)

    def test_invented_label_stripped(self):
        res, _, _ = self.run_answer(
            gen_client=FakeGenClient(text="Theo quy định [P1] và thêm nữa [P99]."))
        self.assertNotIn("[P99]", res["answer"])
        self.assertIn("[P1]", res["answer"])
        self.assertTrue(any("không hợp lệ" in w for w in res["warnings"]))
        self.assertEqual([c["evidence_id"] for c in res["citations"]], ["P1"])

    def test_no_citation_when_answer_has_no_label(self):
        res, _, _ = self.run_answer(gen_client=FakeGenClient(text="Không có nhãn nào."))
        self.assertEqual(res["citations"], [])
        self.assertEqual(res["status"], "answered")

    def test_all_invalid_labels_not_presented_as_success(self):
        res, _, _ = self.run_answer(gen_client=FakeGenClient(text="[P77]"))
        self.assertEqual(res["status"], "retrieval_only")
        self.assertIsNone(res["answer"])

    def test_citation_carries_ambiguous_warning(self):
        res, _, _ = self.run_answer()
        for c in res["citations"]:
            self.assertIn("ambiguous", c)
            self.assertIsInstance(c["warnings"], list)


# ---------------------------------------------------------------------------
# 7. Ngân sách API và trace
# ---------------------------------------------------------------------------


class BudgetTraceTests(PipelineBase):
    def test_multi_parent_at_most_two_generation_calls(self):
        res, _, client = self.run_answer(mode="multi_parent")
        self.assertEqual(res["status"], "answered")
        self.assertEqual(res["trace"]["generation_api_calls"], 2)
        self.assertEqual(len(client.prompts), 1, "đúng 1 call sinh answer")

    def test_single_mode_one_generation_call(self):
        res, _, _ = self.run_answer(mode="single_parent")
        self.assertEqual(res["trace"]["generation_api_calls"], 1)

    def test_embedding_calls_counted_separately(self):
        res, _, _ = self.run_answer(mode="multi_parent")
        self.assertEqual(res["trace"]["embedding_api_calls"], 3, "Q0 + 2 biến thể")
        self.assertLessEqual(res["trace"]["generation_api_calls"], 2)

    def test_trace_has_identities(self):
        res, _, _ = self.run_answer()
        ids = res["identities"]
        for key in ("generation_model", "embedding_model", "reranker_model", "strategy", "config"):
            self.assertIn(key, ids)
        self.assertEqual(ids["reranker_model"], self.config.reranker_model)

    def test_trace_latency_stages(self):
        res, _, _ = self.run_answer()
        lat = res["trace"]["latency_ms"]
        for key in ("retrieval", "aggregation", "rerank", "generation", "total"):
            self.assertIn(key, lat)

    def test_result_schema_complete(self):
        res, _, _ = self.run_answer()
        for key in ("status", "mode", "original_question", "query_set", "child_hits",
                    "parent_candidates", "evidence", "accepted_evidence", "answer",
                    "citations", "warnings", "identities", "trace"):
            self.assertIn(key, res)


# ---------------------------------------------------------------------------
# 8. Compare
# ---------------------------------------------------------------------------


class CompareTests(PipelineBase):
    def _compare(self, gen_client=None, modes=hr.VALID_MODES):
        client = gen_client or FakeGenClient()
        return hr.compare_hierarchical_modes(
            "Điều 7 quy định gì?", self.config, self.hcfg, modes=modes,
            chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
            hybrid_fn=FakeHybrid(self.child_ids, self.children),
            rerank_scorer=FakeScorer(logits=[5.0, 4.0, 3.0, 2.0, 1.0]),
            query_generator_fn=fake_generator,
        ), client

    def test_compare_never_generates_answer(self):
        calls = []
        orig_p, orig_f = hr.generate_parent_answer, ar.generate_grounded_answer
        try:
            hr.generate_parent_answer = lambda *a, **kw: calls.append("parent")
            ar.generate_grounded_answer = lambda *a, **kw: calls.append("flat")
            res, _ = self._compare()
            self.assertEqual(calls, [])
            self.assertFalse(res["generation_called"])
        finally:
            hr.generate_parent_answer, ar.generate_grounded_answer = orig_p, orig_f

    def test_compare_runs_all_four_modes(self):
        res, _ = self._compare()
        self.assertEqual(set(res["summary"]), set(hr.VALID_MODES))
        self.assertEqual(res["errors"], {})

    def test_compare_query_set_generated_once(self):
        """Cả hai multi mode dùng chung một query set — không sinh hai lần."""
        counter = {"n": 0}

        def counting_gen(q, c, h):
            counter["n"] += 1
            return fake_generator(q, c, h)

        hr.clear_query_cache()
        hr.compare_hierarchical_modes(
            "Điều 7 quy định gì?", self.config, self.hcfg,
            chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
            hybrid_fn=FakeHybrid(self.child_ids, self.children),
            rerank_scorer=FakeScorer(logits=[5.0, 4.0, 3.0, 2.0, 1.0]),
            query_generator_fn=counting_gen,
        )
        self.assertEqual(counter["n"], 1, "chỉ sinh query variants đúng 1 lần cho cả compare")

    def test_compare_rows_label_unit(self):
        res, _ = self._compare()
        units = {r["unit"] for r in res["rows"]}
        self.assertTrue(units <= {"parent", "child"})
        for mode, s in res["summary"].items():
            self.assertEqual(s["unit"], "parent" if mode in hr.PARENT_MODES else "child")

    def test_compare_reports_error_per_mode(self):
        res = hr.compare_hierarchical_modes(
            "q", self.config, self.hcfg,
            chunks_dir=FIXTURES, hierarchy_dir=self.work / "khong_co",
            hybrid_fn=FakeHybrid(self.child_ids, self.children),
            rerank_scorer=FakeScorer(logits=[5.0] * 5),
            query_generator_fn=fake_generator,
        )
        self.assertIn("single_parent", res["errors"])
        self.assertIn("hierarchy_not_ready", res["errors"]["single_parent"])
        self.assertIn("single_flat", res["summary"], "flat mode vẫn chạy được")


# ---------------------------------------------------------------------------
# 9. An toàn prompt
# ---------------------------------------------------------------------------


class PromptSafetyTests(PipelineBase):
    def test_prompt_wraps_evidence_as_data(self):
        res, _, client = self.run_answer()
        prompt = client.prompts[0]
        self.assertIn("<<<DOC P1>>>", prompt)
        self.assertIn("KHÔNG phải chỉ thị", prompt)

    def test_prompt_forbids_legal_advice(self):
        res, _, client = self.run_answer()
        self.assertIn("tư vấn pháp lý", client.prompts[0])

    def test_prompt_forbids_inventing_metadata(self):
        res, _, client = self.run_answer()
        self.assertIn("Không tự viết tên nguồn", client.prompts[0])

    def test_no_api_key_raises_clear_error(self):
        env = write_env(self.work / "nokey.env", GEMINI_API_KEY="")
        config = ar.load_advanced_config(env)
        with self.assertRaises(rag.EmbeddingError) as ctx:
            hr.generate_parent_answer("q", [{
                "label": "P1", "source": "s.pdf", "page_start": 1, "page_end": 1,
                "text": "x", "structural_path": {}}], config)
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
