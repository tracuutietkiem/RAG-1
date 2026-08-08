"""tests/test_reranker.py — Test cross-encoder reranker (Bước 07).

Nguyên tắc (SPEC_buoi_08.md mục 7 & 11): TUYỆT ĐỐI không tải model thật,
không dùng mạng. Mọi test đều tiêm `scorer` giả lập qua tham số injection.
Fake reranker chỉ tồn tại trong test — runtime không có fallback giả.
"""

from __future__ import annotations

import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import advanced_rag as ar  # noqa: E402

DIM = 128


def _write_env(path: Path, **overrides) -> Path:
    values = {
        "GEMINI_API_KEY": "fake-key",
        "GEMINI_EMBEDDING_MODEL": "gemini-embedding-2",
        "GEMINI_EMBEDDING_DIM": str(DIM),
        "GEMINI_GENERATION_MODEL": "gemini-3.5-flash-lite",
        "RAG_MAX_DISTANCE": "0.45",
        "BM25_CANDIDATES": "20",
        "SEMANTIC_CANDIDATES": "20",
        "RRF_K": "60",
        "RRF_BM25_WEIGHT": "1.0",
        "RRF_SEMANTIC_WEIGHT": "1.0",
        "RERANK_CANDIDATES": "20",
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


def _fused(chunk_id, fused_rank, text=None, bm25_rank=None, semantic_rank=None):
    return {
        "chunk_id": chunk_id,
        "text": text if text is not None else f"noi dung {chunk_id}",
        "source": "s.pdf",
        "page_start": 1,
        "page_end": 1,
        "bm25_rank": bm25_rank,
        "bm25_score": 1.0 if bm25_rank else None,
        "semantic_rank": semantic_rank,
        "semantic_distance": 0.2 if semantic_rank else None,
        "rrf_score": 1.0 / (60 + fused_rank),
        "fused_rank": fused_rank,
        "matched_by": ["bm25"] if bm25_rank else ["semantic"],
    }


class _SpyScorer:
    """Fake reranker: ghi lại mọi lời gọi để kiểm tra pair/batching."""

    def __init__(self, logits_by_text=None, default=0.0):
        self.logits_by_text = logits_by_text or {}
        self.default = default
        self.calls = []

    def __call__(self, question, texts, config):
        self.calls.append({"question": question, "texts": list(texts), "config": config})
        return [self.logits_by_text.get(t, self.default) for t in texts]


class RerankScoringTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_sigmoid_conversion_correct(self):
        """rerank_score = sigmoid(logit), nằm trong [0,1]."""
        cands = [_fused("c1", 1, text="t1"), _fused("c2", 2, text="t2"), _fused("c3", 3, text="t3")]
        scorer = _SpyScorer({"t1": 2.0, "t2": 0.0, "t3": -2.0})
        out = ar.rerank_candidates("q", cands, self.config, scorer=scorer)
        by_id = {c["chunk_id"]: c for c in out["candidates"]}
        self.assertAlmostEqual(by_id["c1"]["rerank_score"], 1 / (1 + math.exp(-2.0)), places=12)
        self.assertAlmostEqual(by_id["c2"]["rerank_score"], 0.5, places=12)
        self.assertAlmostEqual(by_id["c3"]["rerank_score"], 1 / (1 + math.exp(2.0)), places=12)
        for c in out["candidates"]:
            self.assertGreaterEqual(c["rerank_score"], 0.0)
            self.assertLessEqual(c["rerank_score"], 1.0)

    def test_raw_score_preserved(self):
        cands = [_fused("c1", 1, text="t1")]
        out = ar.rerank_candidates("q", cands, self.config, scorer=_SpyScorer({"t1": 3.5}))
        self.assertEqual(out["candidates"][0]["rerank_raw_score"], 3.5)

    def test_sigmoid_no_overflow_on_extreme_values(self):
        cands = [_fused("c1", 1, text="big"), _fused("c2", 2, text="small")]
        out = ar.rerank_candidates(
            "q", cands, self.config, scorer=_SpyScorer({"big": 1000.0, "small": -1000.0})
        )
        by_id = {c["chunk_id"]: c for c in out["candidates"]}
        self.assertAlmostEqual(by_id["c1"]["rerank_score"], 1.0, places=9)
        self.assertAlmostEqual(by_id["c2"]["rerank_score"], 0.0, places=9)

    def test_one_pair_per_candidate(self):
        cands = [_fused(f"c{i}", i, text=f"t{i}") for i in range(1, 8)]
        scorer = _SpyScorer()
        ar.rerank_candidates("cau hoi", cands, self.config, scorer=scorer)
        all_texts = [t for call in scorer.calls for t in call["texts"]]
        self.assertEqual(len(all_texts), 7, "Đúng 1 cặp (question, text) cho mỗi candidate")
        self.assertEqual(sorted(all_texts), sorted(c["text"] for c in cands))

    def test_question_passed_to_scorer(self):
        scorer = _SpyScorer()
        ar.rerank_candidates("Điều 7 quy định gì?", [_fused("c1", 1)], self.config, scorer=scorer)
        self.assertEqual(scorer.calls[0]["question"], "Điều 7 quy định gì?")

    def test_scorer_count_mismatch_raises_unavailable(self):
        def bad_scorer(question, texts, config):
            return [0.0]  # thiếu score

        with self.assertRaises(ar.RerankerUnavailableError):
            ar.rerank_candidates("q", [_fused("c1", 1), _fused("c2", 2)], self.config, scorer=bad_scorer)

    def test_empty_candidates_returns_empty(self):
        out = ar.rerank_candidates("q", [], self.config, scorer=_SpyScorer())
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["reranked_count"], 0)


class RerankOrderingTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_reorders_by_rerank_score(self):
        """Candidate xếp chót ở RRF nhưng reranker cho điểm cao phải lên đầu."""
        cands = [_fused("low_rrf", 5, text="best"), _fused("top_rrf", 1, text="worst")]
        out = ar.rerank_candidates(
            "q", cands, self.config, scorer=_SpyScorer({"best": 5.0, "worst": -5.0})
        )
        self.assertEqual(out["candidates"][0]["chunk_id"], "low_rrf")
        self.assertEqual(out["candidates"][0]["rerank_rank"], 1)

    def test_rank_change_computed_correctly(self):
        cands = [_fused("a", 3, text="ta"), _fused("b", 1, text="tb")]
        out = ar.rerank_candidates("q", cands, self.config, scorer=_SpyScorer({"ta": 9.0, "tb": 1.0}))
        by_id = {c["chunk_id"]: c for c in out["candidates"]}
        self.assertEqual(by_id["a"]["rerank_rank"], 1)
        self.assertEqual(by_id["a"]["rank_change"], 3 - 1, "fused 3 -> rerank 1 = +2 (đẩy lên)")
        self.assertEqual(by_id["b"]["rerank_rank"], 2)
        self.assertEqual(by_id["b"]["rank_change"], 1 - 2, "fused 1 -> rerank 2 = -1 (đẩy xuống)")

    def test_rerank_rank_sequential_from_one(self):
        cands = [_fused(f"c{i}", i, text=f"t{i}") for i in range(1, 5)]
        out = ar.rerank_candidates("q", cands, self.config, scorer=_SpyScorer())
        self.assertEqual([c["rerank_rank"] for c in out["candidates"]], [1, 2, 3, 4])

    def test_tie_break_by_fused_rank_then_chunk_id(self):
        """Cùng rerank_score -> fused_rank nhỏ hơn trước, rồi tới chunk_id."""
        cands = [
            _fused("z", 2, text="same"),
            _fused("a", 5, text="same"),
            _fused("m", 2, text="same"),
        ]
        out = ar.rerank_candidates("q", cands, self.config, scorer=_SpyScorer(default=1.0))
        ids = [c["chunk_id"] for c in out["candidates"]]
        self.assertEqual(ids, ["m", "z", "a"], "fused_rank 2 (m,z theo chunk_id) trước fused_rank 5 (a)")

    def test_deterministic_across_runs(self):
        cands = [_fused(f"c{i}", i, text="same") for i in range(1, 6)]
        first = [c["chunk_id"] for c in ar.rerank_candidates("q", cands, self.config, scorer=_SpyScorer())["candidates"]]
        second = [c["chunk_id"] for c in ar.rerank_candidates("q", cands, self.config, scorer=_SpyScorer())["candidates"]]
        self.assertEqual(first, second)


class RerankLimitTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_only_reranks_up_to_rerank_candidates(self):
        config = ar.load_advanced_config(
            _write_env(self.work / ".env", RERANK_CANDIDATES="3", FINAL_TOP_K="3")
        )
        cands = [_fused(f"c{i}", i, text=f"t{i}") for i in range(1, 11)]
        scorer = _SpyScorer()
        out = ar.rerank_candidates("q", cands, config, scorer=scorer)
        scored_texts = [t for call in scorer.calls for t in call["texts"]]
        self.assertEqual(len(scored_texts), 3, "Chỉ rerank 3 candidate đầu theo fused_rank")
        self.assertEqual(sorted(scored_texts), ["t1", "t2", "t3"])
        self.assertEqual(out["reranked_count"], 3)

    def test_fewer_candidates_than_limit_still_works(self):
        """Corpus nhỏ / ít candidate vẫn chạy bình thường, không lỗi."""
        config = ar.load_advanced_config(
            _write_env(self.work / ".env", RERANK_CANDIDATES="20", FINAL_TOP_K="5")
        )
        cands = [_fused("c1", 1), _fused("c2", 2)]
        out = ar.rerank_candidates("q", cands, config, scorer=_SpyScorer())
        self.assertEqual(out["reranked_count"], 2)
        self.assertEqual(len(out["candidates"]), 2)

    def test_returns_only_final_top_k(self):
        config = ar.load_advanced_config(
            _write_env(self.work / ".env", RERANK_CANDIDATES="10", FINAL_TOP_K="2")
        )
        cands = [_fused(f"c{i}", i, text=f"t{i}") for i in range(1, 9)]
        out = ar.rerank_candidates("q", cands, config, scorer=_SpyScorer())
        self.assertEqual(len(out["candidates"]), 2)
        self.assertEqual(out["reranked_count"], 8, "Vẫn rerank 8, chỉ TRẢ VỀ 2")

    def test_reranks_top_fused_not_input_order(self):
        """Chọn theo fused_rank, không phải thứ tự list đầu vào."""
        config = ar.load_advanced_config(
            _write_env(self.work / ".env", RERANK_CANDIDATES="2", FINAL_TOP_K="2")
        )
        cands = [_fused("last", 9, text="t9"), _fused("first", 1, text="t1"), _fused("second", 2, text="t2")]
        scorer = _SpyScorer()
        ar.rerank_candidates("q", cands, config, scorer=scorer)
        scored = [t for call in scorer.calls for t in call["texts"]]
        self.assertEqual(sorted(scored), ["t1", "t2"])

    def test_batch_size_does_not_change_result_count(self):
        for batch in ("1", "4", "64"):
            with self.subTest(batch=batch):
                config = ar.load_advanced_config(_write_env(self.work / f"{batch}.env", RERANK_BATCH_SIZE=batch))
                cands = [_fused(f"c{i}", i, text=f"t{i}") for i in range(1, 8)]
                scorer = _SpyScorer()
                out = ar.rerank_candidates("q", cands, config, scorer=scorer)
                scored = [t for call in scorer.calls for t in call["texts"]]
                self.assertEqual(len(scored), 7, "Batch size không được đổi số cặp được chấm")
                self.assertEqual(len(out["candidates"]), 5)


class RerankFailureTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_scorer_failure_propagates_no_silent_fallback(self):
        """Model lỗi KHÔNG được âm thầm trả kết quả RRF."""

        def broken_scorer(question, texts, config):
            raise ar.RerankerUnavailableError("mô phỏng model tải lỗi")

        with self.assertRaises(ar.RerankerUnavailableError):
            ar.rerank_candidates("q", [_fused("c1", 1)], self.config, scorer=broken_scorer)

    def test_cuda_requested_but_unavailable_fails_clearly(self):
        config = ar.load_advanced_config(_write_env(self.work / "cuda.env", RERANK_DEVICE="cuda"))

        class _FakeTorch:
            class cuda:
                @staticmethod
                def is_available():
                    return False

        original = sys.modules.get("torch")
        sys.modules["torch"] = _FakeTorch
        try:
            with self.assertRaises(ar.RerankerUnavailableError) as ctx:
                ar._resolve_device(config.rerank_device)
            self.assertIn("CUDA", str(ctx.exception))
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    def test_auto_device_falls_back_to_cpu(self):
        class _FakeTorch:
            class cuda:
                @staticmethod
                def is_available():
                    return False

        original = sys.modules.get("torch")
        sys.modules["torch"] = _FakeTorch
        try:
            self.assertEqual(ar._resolve_device("auto"), "cpu")
            self.assertEqual(ar._resolve_device("cpu"), "cpu")
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)


class LazyLoadTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_rerank_with_injected_scorer_never_loads_model(self):
        """Có scorer tiêm vào thì load_reranker KHÔNG được gọi."""
        calls = []
        original = ar.load_reranker
        try:
            ar.load_reranker = lambda config: calls.append(1)
            ar.rerank_candidates("q", [_fused("c1", 1)], self.config, scorer=_SpyScorer())
            self.assertEqual(calls, [], "Không được load model khi đã tiêm scorer")
        finally:
            ar.load_reranker = original

    def test_no_module_level_model_import(self):
        source = (Path(__file__).resolve().parent.parent / "advanced_rag.py").read_text(encoding="utf-8")
        offenders = [
            line
            for line in source.splitlines()
            if (line.startswith("import ") or line.startswith("from "))
            and ("torch" in line or "transformers" in line)
        ]
        self.assertEqual(offenders, [], f"transformers/torch chỉ được import trong hàm, không ở module level: {offenders}")

    def test_status_functions_do_not_load_model(self):
        """reranker_cache_exists chỉ đọc filesystem, không load model."""
        calls = []
        original = ar.load_reranker
        try:
            ar.load_reranker = lambda config: calls.append(1)
            ar.reranker_cache_exists(self.config)
            self.assertEqual(calls, [])
        finally:
            ar.load_reranker = original

    def test_trust_remote_code_never_enabled(self):
        source = (Path(__file__).resolve().parent.parent / "advanced_rag.py").read_text(encoding="utf-8")
        self.assertNotIn("trust_remote_code=True", source)
        self.assertIn("trust_remote_code=False", source)

    def test_cache_dir_inside_buoi_08_storage(self):
        cache_dir = ar._reranker_cache_dir()
        self.assertEqual(cache_dir.name, "huggingface")
        self.assertEqual(cache_dir.parent.name, "storage")
        self.assertEqual(cache_dir.parent.parent.name, "buoi_08")

    def test_result_reports_model_and_latency(self):
        out = ar.rerank_candidates("q", [_fused("c1", 1)], self.config, scorer=_SpyScorer())
        self.assertEqual(out["reranker_model"], "BAAI/bge-reranker-v2-m3")
        self.assertIsInstance(out["rerank_latency_ms"], float)
        self.assertEqual(out["candidates"][0]["reranker_model"], "BAAI/bge-reranker-v2-m3")


if __name__ == "__main__":
    unittest.main()
