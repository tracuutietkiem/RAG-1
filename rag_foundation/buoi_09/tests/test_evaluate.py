"""tests/test_evaluate.py — Test evaluator (Bước 09).

Offline: fixture + fake retriever/scorer/generator. Không mạng, không model,
không đọc `.env` thật, không đụng storage Buổi 05–08.
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
import evaluate as ev  # noqa: E402
import hierarchical_rag as hr  # noqa: E402
import rag  # noqa: E402

from test_answer_pipeline import FakeScorer, fake_generator  # noqa: E402
from test_hierarchy import write_env  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Metric thuần — tính tay
# ---------------------------------------------------------------------------


class MetricTests(unittest.TestCase):
    def test_recall_hand_computed(self):
        # 2 trong 4 nhãn nằm trong top-5
        self.assertAlmostEqual(
            ev.recall_at_k(["a", "x", "b", "y", "z"], {"a", "b", "c", "d"}, 5), 0.5)

    def test_recall_respects_k(self):
        self.assertAlmostEqual(ev.recall_at_k(["x", "x", "x", "a"], {"a"}, 3), 0.0)
        self.assertAlmostEqual(ev.recall_at_k(["x", "x", "x", "a"], {"a"}, 4), 1.0)

    def test_no_labels_returns_none_not_zero(self):
        """Câu out_of_scope: None nghĩa là 'không có gì để trượt', khác hẳn 0.0."""
        for fn in (ev.recall_at_k, ev.mrr_at_k, ev.ndcg_at_k):
            self.assertIsNone(fn(["a", "b"], set(), 5), fn.__name__)

    def test_mrr_uses_first_hit(self):
        self.assertAlmostEqual(ev.mrr_at_k(["x", "y", "a"], {"a", "b"}, 5), 1 / 3)
        self.assertAlmostEqual(ev.mrr_at_k(["a"], {"a"}, 5), 1.0)
        self.assertAlmostEqual(ev.mrr_at_k(["x", "y"], {"a"}, 5), 0.0)

    def test_ndcg_perfect_is_one(self):
        self.assertAlmostEqual(ev.ndcg_at_k(["a", "b"], {"a", "b"}, 5), 1.0)

    def test_ndcg_hand_computed(self):
        """Hit ở hạng 2, 1 nhãn: DCG = 1/log2(3), IDCG = 1/log2(2) = 1."""
        import math
        self.assertAlmostEqual(ev.ndcg_at_k(["x", "a"], {"a"}, 5), 1 / math.log2(3), places=12)

    def test_ndcg_idcg_capped_by_k(self):
        """5 nhãn nhưng K=2: IDCG chỉ tính 2 vị trí, tránh nDCG bị ép nhỏ oan."""
        self.assertAlmostEqual(ev.ndcg_at_k(["a", "b"], {"a", "b", "c", "d", "e"}, 2), 1.0)

    def test_mean_and_p50_ignore_none(self):
        self.assertAlmostEqual(ev._mean([1.0, None, 3.0]), 2.0)
        # bỏ None còn [1, 3, 5] -> trung vị 3.0
        self.assertAlmostEqual(ev._p50([5.0, None, 1.0, 3.0]), 3.0)
        self.assertIsNone(ev._mean([None, None]))


# ---------------------------------------------------------------------------
# Question set
# ---------------------------------------------------------------------------


class QuestionSetTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, data):
        p = self.dir / "q.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def _item(self, qid="Q01", **over):
        item = {"question_id": qid, "question": "hỏi gì đó", "question_type": "exact",
                "relevant_child_ids": [], "relevant_parent_ids": [],
                "needs_human_review": True}
        item.update(over)
        return item

    def test_loads_valid(self):
        qs = ev.load_questions(self._write([self._item()]))
        self.assertEqual(qs[0]["scope"], "in_scope", "mặc định in_scope")

    def test_missing_field_fails(self):
        bad = self._item()
        del bad["relevant_parent_ids"]
        with self.assertRaises(rag.DataError) as ctx:
            ev.load_questions(self._write([bad]))
        self.assertIn("relevant_parent_ids", str(ctx.exception))

    def test_duplicate_id_fails(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self._write([self._item("Q01"), self._item("Q01")]))

    def test_missing_file_fails_clearly(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self.dir / "khong_co.json")

    def test_broken_json_fails(self):
        p = self.dir / "x.json"
        p.write_text("{ hỏng", encoding="utf-8")
        with self.assertRaises(rag.DataError):
            ev.load_questions(p)

    def test_stale_parent_id_fails(self):
        """Nhãn trỏ parent không còn tồn tại phải FAIL, không im lặng tính 0."""
        qs = [self._item(relevant_parent_ids=["p_da_bien_mat"])]
        with self.assertRaises(rag.DataError) as ctx:
            ev.validate_gold_against_store(qs, {}, {"p_that": {}})
        self.assertIn("stale", str(ctx.exception))

    def test_stale_child_id_fails(self):
        qs = [self._item(relevant_child_ids=["c_ma"])]
        with self.assertRaises(rag.DataError):
            ev.validate_gold_against_store(qs, {"c_that": {}}, {})

    def test_valid_gold_passes(self):
        qs = [self._item(relevant_child_ids=["c1"], relevant_parent_ids=["p1"])]
        ev.validate_gold_against_store(qs, {"c1": {}}, {"p1": {}})  # không raise


# ---------------------------------------------------------------------------
# Evaluate end-to-end với fake
# ---------------------------------------------------------------------------


class FakeHybridFixture:
    def __init__(self, children, order):
        self.children = children
        self.order = order

    def __call__(self, question, config, strategy, bm25_index=None, chunks_dir=None,
                 persist_path=None, client_factory=None):
        cands = []
        for i, cid in enumerate(self.order, start=1):
            c = self.children[cid]
            cands.append({
                "chunk_id": cid, "text": c["text"], "source": c["source"],
                "page_start": c["page_start"], "page_end": c["page_end"],
                "bm25_rank": i, "bm25_score": 1.0, "semantic_rank": i,
                "semantic_distance": 0.1, "rrf_score": 1.0 / (60 + i),
                "fused_rank": i, "matched_by": ["bm25"],
            })
        return {"candidates": cands, "trace": {}}


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        env = write_env(self.work / ".env", GEMINI_API_KEY="fake")
        self.config = ar.load_advanced_config(env)
        self.hcfg = hr.load_hierarchy_config(env)
        self.hdir = self.work / "h"
        hr.build_hierarchy(self.hcfg, chunks_dir=FIXTURES, hierarchy_dir=self.hdir)
        self.children, self.parents, _ = hr.load_hierarchy_store(self.hdir)
        self.order = sorted(self.children)[:5]
        gold_child = self.order[0]
        gold_parent = self.children[gold_child]["parent_id"]
        self.qpath = self.work / "q.json"
        self.qpath.write_text(json.dumps([
            {"question_id": "Q01", "question": "Điều 7 quy định gì?",
             "question_type": "exact", "scope": "in_scope",
             "relevant_child_ids": [gold_child], "relevant_parent_ids": [gold_parent],
             "needs_human_review": True, "notes": ""},
            {"question_id": "Q02", "question": "Lãi suất hôm nay?",
             "question_type": "out_of_scope", "scope": "out_of_scope",
             "relevant_child_ids": [], "relevant_parent_ids": [],
             "needs_human_review": True, "notes": ""},
        ], ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _run(self, modes=hr.VALID_MODES, **kw):
        return ev.evaluate(
            k=5, modes=modes, questions_path=self.qpath,
            chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
            config=self.config, hcfg=self.hcfg,
            hybrid_fn=FakeHybridFixture(self.children, self.order),
            rerank_scorer=FakeScorer(logits=[5.0, 4.0, 3.0, 2.0, 1.0]),
            query_generator_fn=fake_generator, **kw,
        )

    def test_never_calls_answer_generation(self):
        calls = []
        orig_p, orig_f = hr.generate_parent_answer, ar.generate_grounded_answer
        try:
            hr.generate_parent_answer = lambda *a, **kw: calls.append("p")
            ar.generate_grounded_answer = lambda *a, **kw: calls.append("f")
            report = self._run()
            self.assertEqual(calls, [])
            self.assertFalse(report["generation_called"])
        finally:
            hr.generate_parent_answer, ar.generate_grounded_answer = orig_p, orig_f

    def test_all_modes_evaluated(self):
        report = self._run()
        self.assertEqual(set(report["per_mode"]), set(hr.VALID_MODES))
        self.assertEqual(report["failures"], [])

    def test_out_of_scope_excluded_from_quality_metrics(self):
        report = self._run()
        self.assertEqual(report["question_counts"]["in_scope"], 1)
        self.assertEqual(report["question_counts"]["out_of_scope"], 1)
        for mode in hr.VALID_MODES:
            self.assertEqual(report["per_mode"][mode]["questions_scored"], 1)
            self.assertEqual(report["per_mode"][mode]["questions_run"], 2)

    def test_flat_mode_gets_parent_recall_via_registry(self):
        """flat mode trả child nhưng vẫn quy đổi được sang parent để so cùng thang."""
        report = self._run(modes=("single_flat",))
        row = report["per_question"][0]["by_mode"]["single_flat"]
        self.assertIsNotNone(row["parent_recall_at_k"])

    def test_parent_mode_child_recall_from_supporting(self):
        report = self._run(modes=("multi_parent",))
        row = report["per_question"][0]["by_mode"]["multi_parent"]
        self.assertIsNotNone(row["child_recall_at_k"])

    def test_api_calls_separated(self):
        report = self._run(modes=("multi_parent",))
        m = report["per_mode"]["multi_parent"]
        self.assertGreater(m["embedding_api_calls_total"], 0)
        self.assertLessEqual(m["generation_api_calls_total"], 2 * 2,
                             "tối đa 1 call sinh query mỗi câu hỏi × 2 câu")

    def test_expansion_factor_recorded(self):
        report = self._run(modes=("multi_parent",))
        self.assertIsNotNone(report["per_mode"]["multi_parent"]["expansion_factor_mean"])

    def test_human_review_warning_present(self):
        report = self._run()
        self.assertEqual(report["needs_human_review_count"], 2)
        self.assertIn("KHÔNG dùng để kết luận", report["human_review_warning"])

    def test_identities_recorded(self):
        report = self._run()
        ids = report["identities"]
        for key in ("embedding_model", "reranker_model", "strategy", "hierarchy_built_at",
                    "hierarchy_counts", "corpus_files", "config"):
            self.assertIn(key, ids)

    def test_mode_error_recorded_not_crash(self):
        report = ev.evaluate(
            k=5, modes=("single_flat",), questions_path=self.qpath,
            chunks_dir=FIXTURES, hierarchy_dir=self.hdir,
            config=self.config, hcfg=self.hcfg,
            hybrid_fn=FakeHybridFixture(self.children, self.order),
            rerank_scorer=FakeScorer(raises=ar.RerankerUnavailableError("hỏng")),
            query_generator_fn=fake_generator,
        )
        self.assertTrue(report["failures"])
        self.assertEqual(report["per_mode"]["single_flat"]["questions_run"], 0)

    def test_stale_gold_blocks_evaluation(self):
        self.qpath.write_text(json.dumps([{
            "question_id": "Q01", "question": "x", "question_type": "exact",
            "scope": "in_scope", "relevant_child_ids": [], "relevant_parent_ids": ["p_ma"],
            "needs_human_review": True}], ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(rag.DataError):
            self._run()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ReportWriteTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.report = {"timestamp": "2026-08-08T10:00:00+00:00", "per_mode": {},
                       "per_question": [], "identities": {}, "modes": []}

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_writes_report_and_latest(self):
        path = ev.save_report(self.report, self.dir)
        self.assertTrue(path.exists())
        self.assertTrue((self.dir / "latest_report.json").exists())

    def test_latest_matches_report(self):
        path = ev.save_report(self.report, self.dir)
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8")),
            json.loads((self.dir / "latest_report.json").read_text(encoding="utf-8")))

    def test_incomplete_report_rejected_and_latest_untouched(self):
        ev.save_report(self.report, self.dir)
        before = (self.dir / "latest_report.json").read_text(encoding="utf-8")
        with self.assertRaises(rag.DataError):
            ev.save_report({"timestamp": "x"}, self.dir)
        self.assertEqual((self.dir / "latest_report.json").read_text(encoding="utf-8"), before)

    def test_no_temp_file_left(self):
        ev.save_report(self.report, self.dir)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
