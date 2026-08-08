"""tests/test_evaluate.py — Test metric và evaluator (Bước 10).

Các công thức Recall@K / MRR@K / nDCG@K được kiểm bằng ví dụ ranking nhỏ
TÍNH TAY ĐƯỢC, không phụ thuộc pipeline. Phần evaluator chạy hoàn toàn
offline: embedding và reranker đều tiêm giả lập, Chroma dùng thư mục tạm.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import advanced_rag as ar  # noqa: E402
import evaluate as ev  # noqa: E402
import rag  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DIM = 128


# ---------------------------------------------------------------------------
# Metric — ví dụ tính tay
# ---------------------------------------------------------------------------


class RecallAtKTests(unittest.TestCase):
    def test_all_relevant_found(self):
        self.assertEqual(ev.recall_at_k(["a", "b", "c"], {"a", "b"}, 3), 1.0)

    def test_half_relevant_found(self):
        """2 tài liệu liên quan, tìm được 1 -> 1/2 = 0.5."""
        self.assertEqual(ev.recall_at_k(["a", "x", "y"], {"a", "b"}, 3), 0.5)

    def test_none_found(self):
        self.assertEqual(ev.recall_at_k(["x", "y", "z"], {"a", "b"}, 3), 0.0)

    def test_cutoff_respected(self):
        """'b' ở hạng 4, k=3 -> không tính. 1/2 = 0.5."""
        self.assertEqual(ev.recall_at_k(["a", "x", "y", "b"], {"a", "b"}, 3), 0.5)

    def test_no_relevant_returns_zero(self):
        self.assertEqual(ev.recall_at_k(["a", "b"], set(), 3), 0.0)

    def test_one_third(self):
        self.assertAlmostEqual(ev.recall_at_k(["a"], {"a", "b", "c"}, 5), 1 / 3, places=10)


class MRRAtKTests(unittest.TestCase):
    def test_first_position(self):
        self.assertEqual(ev.mrr_at_k(["a", "x"], {"a"}, 5), 1.0)

    def test_second_position(self):
        self.assertEqual(ev.mrr_at_k(["x", "a"], {"a"}, 5), 0.5)

    def test_third_position(self):
        self.assertAlmostEqual(ev.mrr_at_k(["x", "y", "a"], {"a"}, 5), 1 / 3, places=10)

    def test_uses_first_relevant_only(self):
        """Có 2 tài liệu liên quan ở hạng 2 và 3 -> chỉ tính hạng 2 = 0.5."""
        self.assertEqual(ev.mrr_at_k(["x", "a", "b"], {"a", "b"}, 5), 0.5)

    def test_not_found_in_k(self):
        self.assertEqual(ev.mrr_at_k(["x", "y", "z", "a"], {"a"}, 3), 0.0)

    def test_no_relevant_returns_zero(self):
        self.assertEqual(ev.mrr_at_k(["a"], set(), 3), 0.0)


class NDCGAtKTests(unittest.TestCase):
    def test_perfect_ranking_is_one(self):
        self.assertAlmostEqual(ev.ndcg_at_k(["a", "b", "x"], {"a", "b"}, 3), 1.0, places=10)

    def test_single_relevant_at_position_two(self):
        """
        DCG  = 1/log2(3) = 0.6309297...
        IDCG = 1/log2(2) = 1.0
        nDCG = 0.6309297...
        """
        expected = (1 / math.log2(3)) / 1.0
        self.assertAlmostEqual(ev.ndcg_at_k(["x", "a"], {"a"}, 5), expected, places=10)
        self.assertAlmostEqual(expected, 0.63092975, places=7)

    def test_two_relevant_split_positions(self):
        """
        Ranking: [a, x, b] với relevant = {a, b}
        DCG  = 1/log2(2) + 1/log2(4) = 1.0 + 0.5 = 1.5
        IDCG = 1/log2(2) + 1/log2(3) = 1.0 + 0.63092975 = 1.63092975
        nDCG = 1.5 / 1.63092975 = 0.9197207...
        """
        dcg = 1 / math.log2(2) + 1 / math.log2(4)
        idcg = 1 / math.log2(2) + 1 / math.log2(3)
        self.assertAlmostEqual(ev.ndcg_at_k(["a", "x", "b"], {"a", "b"}, 3), dcg / idcg, places=10)
        self.assertAlmostEqual(dcg / idcg, 0.91972074, places=7)

    def test_none_relevant_is_zero(self):
        self.assertEqual(ev.ndcg_at_k(["x", "y"], {"a"}, 3), 0.0)

    def test_cutoff_respected(self):
        self.assertEqual(ev.ndcg_at_k(["x", "y", "z", "a"], {"a"}, 3), 0.0)

    def test_idcg_capped_by_k(self):
        """
        3 tài liệu liên quan nhưng k=1: IDCG chỉ tính 1 vị trí, nên tìm đúng 1
        cái ở hạng 1 vẫn cho nDCG = 1.0.
        """
        self.assertAlmostEqual(ev.ndcg_at_k(["a"], {"a", "b", "c"}, 1), 1.0, places=10)

    def test_no_relevant_returns_zero(self):
        self.assertEqual(ev.ndcg_at_k(["a"], set(), 3), 0.0)

    def test_ndcg_between_zero_and_one(self):
        for retrieved, relevant in (
            (["a", "b", "c"], {"a"}),
            (["c", "b", "a"], {"a", "b"}),
            (["x", "y", "a"], {"a", "b", "c"}),
        ):
            with self.subTest(retrieved=retrieved):
                value = ev.ndcg_at_k(retrieved, relevant, 3)
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)


# ---------------------------------------------------------------------------
# Gold labels
# ---------------------------------------------------------------------------


class LoadQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write(self, data) -> Path:
        p = self.work / "questions.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def _valid(self, **overrides):
        q = {
            "query_id": "Q01",
            "question": "câu hỏi",
            "relevant_chunk_ids": ["c1"],
            "scope": "in_scope",
            "needs_human_review": True,
        }
        q.update(overrides)
        return q

    def test_real_eval_file_is_valid(self):
        questions = ev.load_questions()
        self.assertGreaterEqual(len(questions), 8, "Cần tối thiểu 8 câu hỏi mẫu")
        self.assertTrue(all(q["needs_human_review"] for q in questions),
                        "Gold labels ban đầu phải đánh dấu needs_human_review=true")

    def test_missing_file_raises(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self.work / "khong_ton_tai.json")

    def test_invalid_json_raises(self):
        p = self.work / "bad.json"
        p.write_text("{khong hop le", encoding="utf-8")
        with self.assertRaises(rag.DataError):
            ev.load_questions(p)

    def test_missing_field_raises(self):
        q = self._valid()
        del q["scope"]
        with self.assertRaises(rag.DataError):
            ev.load_questions(self._write([q]))

    def test_invalid_scope_raises(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self._write([self._valid(scope="ngoai_le")]))

    def test_duplicate_query_id_raises(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self._write([self._valid(), self._valid()]))

    def test_empty_list_raises(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self._write([]))

    def test_relevant_ids_must_be_list(self):
        with self.assertRaises(rag.DataError):
            ev.load_questions(self._write([self._valid(relevant_chunk_ids="c1")]))


# ---------------------------------------------------------------------------
# Evaluator — offline, mock toàn bộ
# ---------------------------------------------------------------------------


def _vector(text, dim, salt=""):
    h = hashlib.sha256((salt + text).encode("utf-8")).digest()
    return [((h[i % len(h)] / 255.0) - 0.5) + (i + 1) * 1e-6 for i in range(dim)]


class _FakeModels:
    def __init__(self, dim, salt):
        self.dim, self.salt = dim, salt

    def embed_content(self, model, contents, config):
        return type("R", (), {"embeddings": [type("E", (), {"values": _vector(contents, self.dim, self.salt)})]})

    def generate_content(self, model, contents):
        raise AssertionError("evaluate.py TUYỆT ĐỐI không được gọi generation")


class _FakeClient:
    def __init__(self, dim, salt):
        self.models = _FakeModels(dim, salt)


def _write_env(path: Path, **overrides) -> Path:
    values = {
        "GEMINI_API_KEY": "fake-key",
        "GEMINI_EMBEDDING_MODEL": "gemini-embedding-2",
        "GEMINI_EMBEDDING_DIM": str(DIM),
        "GEMINI_GENERATION_MODEL": "gemini-3.5-flash-lite",
        "RAG_MAX_DISTANCE": "2.0",
        "BM25_CANDIDATES": "5",
        "SEMANTIC_CANDIDATES": "5",
        "RRF_K": "60",
        "RRF_BM25_WEIGHT": "1.0",
        "RRF_SEMANTIC_WEIGHT": "1.0",
        "RERANK_CANDIDATES": "8",
        "FINAL_TOP_K": "5",
        "RERANKER_MODEL": "BAAI/bge-reranker-v2-m3",
        "RERANKER_MAX_LENGTH": "512",
        "RERANK_BATCH_SIZE": "4",
        "RERANK_MIN_SCORE": "0.50",
        "RERANK_DEVICE": "auto",
    }
    values.update(overrides)
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
    return path


def _scorer(question, texts, config):
    return [1.0] * len(texts)


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chroma = self.work / "chroma"
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))
        ar.prepare_semantic(
            "hierarchical", self.config, chunks_dir=FIXTURE_DIR,
            persist_path=self.chroma, client_factory=lambda k: _FakeClient(DIM, "doc"),
        )
        self.questions = ev.load_questions()

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _evaluate(self, k=5, modes=ar.VALID_MODES, questions=None):
        return ev.evaluate(
            questions if questions is not None else self.questions,
            self.config, "hierarchical", k, modes=modes,
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            embed_client_factory=lambda key: _FakeClient(DIM, "query"),
            rerank_scorer=_scorer,
        )

    def test_never_calls_generation(self):
        """_FakeModels.generate_content sẽ raise nếu bị gọi."""
        calls = []
        original = ar.generate_grounded_answer
        try:
            ar.generate_grounded_answer = lambda *a, **kw: calls.append(1)
            report = self._evaluate()
            self.assertEqual(calls, [])
            self.assertFalse(report["generation_called"])
        finally:
            ar.generate_grounded_answer = original

    def test_all_modes_evaluated(self):
        report = self._evaluate()
        self.assertEqual(set(report["metrics_by_mode"].keys()), set(ar.VALID_MODES))

    def test_metrics_present_and_in_range(self):
        report = self._evaluate(k=5)
        for mode, m in report["metrics_by_mode"].items():
            with self.subTest(mode=mode):
                for key in ("recall@5", "mrr@5", "ndcg@5"):
                    self.assertIn(key, m)
                    self.assertIsNotNone(m[key], "Phải có ít nhất 1 câu hỏi in_scope được chấm")
                    self.assertGreaterEqual(m[key], 0.0)
                    self.assertLessEqual(m[key], 1.0)

    def test_latency_reported(self):
        report = self._evaluate()
        for m in report["metrics_by_mode"].values():
            self.assertIsInstance(m["latency_mean_ms"], float)
            self.assertIsInstance(m["latency_p50_ms"], float)

    def test_same_k_and_corpus_for_all_modes(self):
        """So sánh công bằng: mọi mode dùng cùng corpus, cùng câu hỏi, cùng k."""
        report = self._evaluate(k=3)
        self.assertEqual(report["k"], 3)
        counts = {m["queries_scored"] for m in report["metrics_by_mode"].values()}
        self.assertEqual(len(counts), 1, "Mọi mode phải chấm trên cùng số câu hỏi")

    def test_out_of_scope_excluded_from_metrics(self):
        report = self._evaluate()
        self.assertEqual(report["out_of_scope_count"], 1)
        for m in report["metrics_by_mode"].values():
            self.assertEqual(m["queries_scored"], report["in_scope_count"])

    def test_needs_human_review_warning_present(self):
        report = self._evaluate()
        self.assertTrue(report["needs_human_review"])
        self.assertTrue(any("chưa được chuyên gia" in w.lower() or "CHƯA được chuyên gia" in w
                            for w in report["warnings"]))

    def test_report_records_config_and_model_identity(self):
        report = self._evaluate()
        cfg = report["config"]
        self.assertEqual(cfg["embedding_model"], "gemini-embedding-2")
        self.assertEqual(cfg["reranker_model"], "BAAI/bge-reranker-v2-m3")
        self.assertIn("rrf_k", cfg)
        self.assertIn("timestamp", report)

    def test_failures_recorded_not_silently_skipped(self):
        """Query lỗi phải được ghi rõ, không bỏ âm thầm."""
        def broken(question, texts, config):
            raise ar.RerankerUnavailableError("mô phỏng lỗi")

        report = ev.evaluate(
            self.questions, self.config, "hierarchical", 5, modes=("hybrid_rerank",),
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            embed_client_factory=lambda key: _FakeClient(DIM, "query"),
            rerank_scorer=broken,
        )
        self.assertTrue(report["failures"])
        self.assertEqual(len(report["failures"]), len(self.questions))
        self.assertTrue(any("lỗi" in w.lower() for w in report["warnings"]))

    def test_invalid_k_raises(self):
        for bad in (0, -1, 1.5, True):
            with self.subTest(k=bad):
                with self.assertRaises(rag.DataError):
                    self._evaluate(k=bad)

    def test_per_query_rows_recorded(self):
        report = self._evaluate()
        for mode, rows in report["per_query"].items():
            self.assertEqual(len(rows), len(self.questions))
            for row in rows:
                self.assertIn("query_id", row)
                self.assertIn("retrieved_ids", row)
                self.assertIn("latency_ms", row)

    def test_save_report_writes_json(self):
        report = self._evaluate()
        path = ev.save_report(report, reports_dir=self.work / "reports")
        self.assertTrue(path.exists())
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["strategy"], "hierarchical")
        self.assertIn("metrics_by_mode", loaded)

    def test_bm25_index_built_once(self):
        calls = []
        original = ar.build_bm25_index
        try:
            def spy(chunks):
                calls.append(1)
                return original(chunks)

            ar.build_bm25_index = spy
            self._evaluate()
            self.assertEqual(len(calls), 1, "BM25 index chỉ dựng 1 lần cho toàn bộ đánh giá")
        finally:
            ar.build_bm25_index = original


if __name__ == "__main__":
    unittest.main()
