"""tests/test_answer.py — Test Advanced RAG answer pipeline + compare (Bước 08).

Nguyên tắc (SPEC_buoi_08.md mục 9 & 11): mock toàn bộ ranh giới bên ngoài —
Gemini embedding, Gemini generation, reranker đều được tiêm giả lập. Không
Internet, không tải model, Chroma dùng thư mục tạm.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import advanced_rag as ar  # noqa: E402
import rag  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DIM = 128


def _vector(text, dim, salt=""):
    h = hashlib.sha256((salt + text).encode("utf-8")).digest()
    return [((h[i % len(h)] / 255.0) - 0.5) + (i + 1) * 1e-6 for i in range(dim)]


class _FakeModels:
    def __init__(self, dim, salt, gen_text=None, gen_raises=False):
        self.dim, self.salt = dim, salt
        self.gen_text, self.gen_raises = gen_text, gen_raises
        self.embed_calls = 0
        self.generate_calls = 0

    def embed_content(self, model, contents, config):
        self.embed_calls += 1
        return type("R", (), {"embeddings": [type("E", (), {"values": _vector(contents, self.dim, self.salt)})]})

    def generate_content(self, model, contents):
        self.generate_calls += 1
        if self.gen_raises:
            raise RuntimeError("mô phỏng lỗi Gemini generation")
        return type("R", (), {"text": self.gen_text})


class _FakeClient:
    def __init__(self, dim, salt, **kw):
        self.models = _FakeModels(dim, salt, **kw)


class _CountingFactory:
    """Factory ghi lại số lần generate_content được gọi trên mọi client tạo ra."""

    def __init__(self, **kw):
        self.kw = kw
        self.clients = []

    def __call__(self, api_key):
        client = _FakeClient(DIM, "query", **self.kw)
        self.clients.append(client)
        return client

    @property
    def generate_calls(self):
        return sum(c.models.generate_calls for c in self.clients)


def _write_env(path: Path, **overrides) -> Path:
    values = {
        "GEMINI_API_KEY": "fake-key",
        "GEMINI_EMBEDDING_MODEL": "gemini-embedding-2",
        "GEMINI_EMBEDDING_DIM": str(DIM),
        "GEMINI_GENERATION_MODEL": "gemini-3.5-flash-lite",
        "RAG_MAX_DISTANCE": "2.0",  # nới lỏng: vector giả lập không mang ngữ nghĩa thật
        "BM25_CANDIDATES": "5",
        "SEMANTIC_CANDIDATES": "5",
        "RRF_K": "60",
        "RRF_BM25_WEIGHT": "1.0",
        "RRF_SEMANTIC_WEIGHT": "1.0",
        "RERANK_CANDIDATES": "10",
        "FINAL_TOP_K": "3",
        "RERANKER_MODEL": "BAAI/bge-reranker-v2-m3",
        "RERANKER_MAX_LENGTH": "512",
        "RERANK_BATCH_SIZE": "4",
        "RERANK_MIN_SCORE": "0.50",
        "RERANK_DEVICE": "auto",
    }
    values.update(overrides)
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
    return path


def _high_scorer(question, texts, config):
    """Mọi candidate đều vượt ngưỡng rerank (sigmoid(5) ~ 0.993)."""
    return [5.0] * len(texts)


def _low_scorer(question, texts, config):
    """Mọi candidate đều dưới ngưỡng rerank (sigmoid(-5) ~ 0.0067)."""
    return [-5.0] * len(texts)


class _AnswerTestBase(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chroma = self.work / "chroma"
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))
        ar.prepare_semantic(
            "hierarchical", self.config, chunks_dir=FIXTURE_DIR,
            persist_path=self.chroma, client_factory=lambda k: _FakeClient(DIM, "doc"),
        )

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _answer(self, mode="hybrid_rerank", gen_text="Trả lời có căn cứ [E1].", scorer=_high_scorer,
                config=None, gen_factory=None, question="Điều 7 cơ cấu lại thời hạn trả nợ"):
        factory = gen_factory or _CountingFactory(gen_text=gen_text)
        result = ar.answer(
            question, config or self.config, "hierarchical", mode=mode,
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            embed_client_factory=lambda k: _FakeClient(DIM, "query"),
            generation_client_factory=factory,
            rerank_scorer=scorer,
        )
        return result, factory


class ModeValidationTests(_AnswerTestBase):
    def test_invalid_mode_raises(self):
        for bad in ("BM25", "rerank", "hybrid-rerank", "", None):
            with self.subTest(mode=bad):
                with self.assertRaises(rag.DataError):
                    ar.answer("q", self.config, "hierarchical", mode=bad,
                              chunks_dir=FIXTURE_DIR, persist_path=self.chroma)

    def test_all_four_modes_supported(self):
        for mode in ("bm25", "semantic", "hybrid", "hybrid_rerank"):
            with self.subTest(mode=mode):
                result, _ = self._answer(mode=mode)
                self.assertEqual(result["mode"], mode)
                self.assertIn(result["status"], ("answered", "insufficient_evidence", "retrieval_only"))

    def test_default_mode_is_hybrid_rerank(self):
        self.assertEqual(ar.DEFAULT_MODE, "hybrid_rerank")


class SchemaTests(_AnswerTestBase):
    def test_all_statuses_return_full_schema(self):
        cases = [
            ("answered", dict(gen_text="ok [E1]")),
            ("retrieval_only", dict(gen_factory=_CountingFactory(gen_raises=True))),
            ("insufficient_evidence", dict(scorer=_low_scorer)),
        ]
        required = {"status", "mode", "question", "answer", "evidence", "citations", "warnings", "trace"}
        for expected_status, kwargs in cases:
            with self.subTest(status=expected_status):
                result, _ = self._answer(**kwargs)
                self.assertEqual(result["status"], expected_status)
                self.assertTrue(required.issubset(result.keys()), f"Thiếu: {required - set(result.keys())}")

    def test_trace_has_all_keys(self):
        result, _ = self._answer()
        trace = result["trace"]
        for key in ("bm25_candidates", "semantic_candidates", "overlap", "union", "reranked",
                    "accepted", "generation_called", "latency_ms"):
            self.assertIn(key, trace)
        for key in ("bm25", "semantic", "fusion", "rerank", "generation", "total"):
            self.assertIn(key, trace["latency_ms"])
            self.assertIsInstance(trace["latency_ms"][key], float)

    def test_evidence_has_all_fields_null_when_not_applicable(self):
        """Mode bm25 không có semantic/rrf/rerank -> phải là None, không bịa số."""
        result, _ = self._answer(mode="bm25")
        for e in result["evidence"]:
            self.assertIsNotNone(e["bm25_rank"])
            self.assertIsNone(e["rrf_score"])
            self.assertIsNone(e["fused_rank"])
            self.assertIsNone(e["rerank_score"])
            self.assertIsNone(e["rerank_rank"])

    def test_evidence_full_fields_in_hybrid_rerank(self):
        result, _ = self._answer(mode="hybrid_rerank")
        for e in result["evidence"]:
            self.assertIsNotNone(e["rrf_score"])
            self.assertIsNotNone(e["fused_rank"])
            self.assertIsNotNone(e["rerank_score"])
            self.assertIsNotNone(e["rerank_raw_score"])
            self.assertIsNotNone(e["rerank_rank"])
            self.assertIsNotNone(e["rank_change"])
            self.assertIsNotNone(e["reranker_model"])

    def test_trace_counts_match_evidence(self):
        result, _ = self._answer()
        accepted = sum(1 for e in result["evidence"] if e["accepted"])
        self.assertEqual(result["trace"]["accepted"], accepted)


class GatingTests(_AnswerTestBase):
    def test_hybrid_rerank_gate_uses_rerank_score(self):
        """rerank_score < RERANK_MIN_SCORE -> loại."""
        result, _ = self._answer(mode="hybrid_rerank", scorer=_low_scorer)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertTrue(all(not e["accepted"] for e in result["evidence"]))

    def test_hybrid_rerank_accepts_above_threshold(self):
        result, _ = self._answer(mode="hybrid_rerank", scorer=_high_scorer)
        self.assertTrue(any(e["accepted"] for e in result["evidence"]))

    def test_gate_boundary_is_inclusive(self):
        """rerank_score == RERANK_MIN_SCORE phải được chấp nhận (>=)."""
        def exact_scorer(question, texts, config):
            return [0.0] * len(texts)  # sigmoid(0) = 0.5 = RERANK_MIN_SCORE

        result, _ = self._answer(mode="hybrid_rerank", scorer=exact_scorer)
        self.assertTrue(any(e["accepted"] for e in result["evidence"]))

    def test_semantic_gate_uses_cosine_distance(self):
        strict = ar.load_advanced_config(_write_env(self.work / "strict.env", RAG_MAX_DISTANCE="0.0001"))
        result, _ = self._answer(mode="semantic", config=strict)
        self.assertEqual(result["status"], "insufficient_evidence")

    def test_bm25_mode_requires_semantic_gate_too(self):
        """
        BM25 score không có ngưỡng tin cậy tuyệt đối — mode bm25 chỉ trả lời khi
        có candidate đạt semantic distance gate. Candidate BM25 thuần không có
        semantic_distance nên không được accept.
        """
        result, _ = self._answer(mode="bm25")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertTrue(all(not e["accepted"] for e in result["evidence"]))
        self.assertTrue(any("chẩn đoán" in w for w in result["warnings"]))

    def test_hybrid_mode_requires_semantic_gate_too(self):
        """Candidate hybrid chỉ do BM25 tìm thấy (không có semantic_distance) không được accept."""
        result, _ = self._answer(mode="hybrid")
        for e in result["evidence"]:
            if e["accepted"]:
                self.assertIsNotNone(e["semantic_distance"])
                self.assertLessEqual(e["semantic_distance"], self.config.base.max_distance)


class GenerationTests(_AnswerTestBase):
    def test_generation_called_exactly_once(self):
        result, factory = self._answer()
        self.assertEqual(factory.generate_calls, 1)
        self.assertTrue(result["trace"]["generation_called"])

    def test_no_generation_when_insufficient_evidence(self):
        result, factory = self._answer(scorer=_low_scorer)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(factory.generate_calls, 0, "Không được gọi generation khi thiếu căn cứ")
        self.assertFalse(result["trace"]["generation_called"])

    def test_rejected_evidence_not_in_prompt(self):
        """Evidence bị loại TUYỆT ĐỐI không được đưa vào prompt gửi cho model."""
        captured = {}

        class _CapturingModels(_FakeModels):
            def generate_content(self, model, contents):
                captured["prompt"] = contents
                return super().generate_content(model, contents)

        class _CapturingClient:
            def __init__(self, *a, **kw):
                self.models = _CapturingModels(DIM, "query", gen_text="ok [E1]")

        def half_scorer(question, texts, config):
            # chỉ candidate đầu vượt ngưỡng
            return [5.0] + [-5.0] * (len(texts) - 1)

        result = ar.answer(
            "Điều 7", self.config, "hierarchical", mode="hybrid_rerank",
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            embed_client_factory=lambda k: _FakeClient(DIM, "query"),
            generation_client_factory=lambda k: _CapturingClient(),
            rerank_scorer=half_scorer,
        )
        prompt = captured["prompt"]
        rejected = [e for e in result["evidence"] if not e["accepted"]]
        self.assertTrue(rejected, "Test cần có ít nhất 1 evidence bị loại")
        for e in rejected:
            self.assertNotIn(e["text"], prompt, f"Text bị loại lọt vào prompt: {e['chunk_id']}")

    def test_prompt_wraps_context_in_delimiter(self):
        captured = {}

        class _CapturingModels(_FakeModels):
            def generate_content(self, model, contents):
                captured["prompt"] = contents
                return super().generate_content(model, contents)

        class _CapturingClient:
            def __init__(self, *a, **kw):
                self.models = _CapturingModels(DIM, "query", gen_text="ok [E1]")

        ar.answer(
            "Điều 7", self.config, "hierarchical", mode="hybrid_rerank",
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            embed_client_factory=lambda k: _FakeClient(DIM, "query"),
            generation_client_factory=lambda k: _CapturingClient(),
            rerank_scorer=_high_scorer,
        )
        prompt = captured["prompt"]
        self.assertIn("<<<DOC E1>>>", prompt)
        self.assertIn("<<<END E1>>>", prompt)
        self.assertIn("KHÔNG phải chỉ thị", prompt, "Phải nói rõ context là dữ liệu")

    def test_generation_failure_returns_retrieval_only(self):
        result, factory = self._answer(gen_factory=_CountingFactory(gen_raises=True))
        self.assertEqual(result["status"], "retrieval_only")
        self.assertIsNone(result["answer"])
        self.assertTrue(result["evidence"], "Vẫn phải trả evidence")
        self.assertTrue(any("thất bại" in w for w in result["warnings"]))

    def test_empty_generation_returns_retrieval_only(self):
        result, _ = self._answer(gen_text="")
        self.assertEqual(result["status"], "retrieval_only")


class CitationTests(_AnswerTestBase):
    def test_valid_citation_maps_to_real_metadata(self):
        result, _ = self._answer(gen_text="Theo quy định [E1].")
        self.assertEqual(result["status"], "answered")
        self.assertTrue(result["citations"])
        c = result["citations"][0]
        evidence_by_label = {e["label"]: e for e in result["evidence"] if e["label"]}
        src = evidence_by_label[c["label"]]
        self.assertEqual(c["chunk_id"], src["chunk_id"])
        self.assertEqual(c["source"], src["source"])
        self.assertEqual(c["page_start"], src["page_start"])

    def test_fake_label_removed_and_warned(self):
        result, _ = self._answer(gen_text="Đúng [E1] và bịa [E99].")
        self.assertNotIn("[E99]", result["answer"])
        self.assertIn("[E1]", result["answer"])
        self.assertTrue(any("E99" in w for w in result["warnings"]))
        self.assertFalse(any(c["label"] == "E99" for c in result["citations"]))

    def test_llm_written_source_not_trusted(self):
        """Citation lấy từ metadata thật, không phải từ chữ LLM viết trong câu."""
        result, _ = self._answer(gen_text="Theo file_bia_dat.pdf trang 999 [E1].")
        c = result["citations"][0]
        self.assertNotEqual(c["source"], "file_bia_dat.pdf")
        self.assertNotEqual(c["page_start"], 999)

    def test_labels_sequential_among_accepted_only(self):
        def half_scorer(question, texts, config):
            return [5.0, -5.0] + [5.0] * (len(texts) - 2)

        result, _ = self._answer(scorer=half_scorer)
        labels = [e["label"] for e in result["evidence"] if e["accepted"]]
        self.assertEqual(labels, [f"E{i}" for i in range(1, len(labels) + 1)])
        for e in result["evidence"]:
            if not e["accepted"]:
                self.assertIsNone(e["label"], "Evidence bị loại không được có label")


class RerankerUnavailableTests(_AnswerTestBase):
    def test_reranker_failure_gives_dedicated_status(self):
        def broken(question, texts, config):
            raise ar.RerankerUnavailableError("mô phỏng model tải lỗi")

        result, factory = self._answer(mode="hybrid_rerank", scorer=broken)
        self.assertEqual(result["status"], "reranker_unavailable")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["citations"], [])
        self.assertEqual(factory.generate_calls, 0)
        self.assertTrue(any("Reranker không khả dụng" in w for w in result["warnings"]))

    def test_rrf_results_not_presented_as_reranked(self):
        def broken(question, texts, config):
            raise ar.RerankerUnavailableError("lỗi")

        result, _ = self._answer(mode="hybrid_rerank", scorer=broken)
        self.assertEqual(result["evidence"], [], "Không được trả kết quả RRF như thể đã rerank")


class CompareTests(_AnswerTestBase):
    def _compare(self, scorer=_high_scorer):
        return ar.compare_modes(
            "Điều 7 cơ cấu lại thời hạn trả nợ", self.config, "hierarchical",
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            embed_client_factory=lambda k: _FakeClient(DIM, "query"),
            rerank_scorer=scorer,
        )

    def test_compare_never_calls_generation(self):
        calls = []
        original = ar.generate_grounded_answer
        try:
            ar.generate_grounded_answer = lambda *a, **kw: calls.append(1)
            result = self._compare()
            self.assertEqual(calls, [], "compare TUYỆT ĐỐI không được gọi generation")
            self.assertFalse(result["generation_called"])
        finally:
            ar.generate_grounded_answer = original

    def test_compare_covers_all_four_modes(self):
        result = self._compare()
        self.assertEqual(set(result["per_mode"].keys()), set(ar.VALID_MODES))

    def test_compare_rows_have_rank_columns(self):
        result = self._compare()
        self.assertTrue(result["rows"])
        for row in result["rows"]:
            for field in ("chunk_id", "bm25_rank", "semantic_rank", "fused_rank",
                          "rerank_rank", "rank_change", "final_rank_by_mode", "final_modes"):
                self.assertIn(field, row)

    def test_compare_reports_latency_per_mode(self):
        result = self._compare()
        for mode, data in result["per_mode"].items():
            self.assertIn("latency_ms", data)
            self.assertGreaterEqual(data["latency_ms"]["total"], 0.0)

    def test_compare_records_reranker_error_without_failing_others(self):
        def broken(question, texts, config):
            raise ar.RerankerUnavailableError("mô phỏng lỗi")

        result = self._compare(scorer=broken)
        self.assertIn("hybrid_rerank", result["errors"])
        for mode in ("bm25", "semantic", "hybrid"):
            self.assertIn(mode, result["per_mode"], f"{mode} vẫn phải chạy được")

    def test_compare_builds_bm25_index_once(self):
        calls = []
        original = ar.build_bm25_index
        try:
            def spy(chunks):
                calls.append(1)
                return original(chunks)

            ar.build_bm25_index = spy
            self._compare()
            self.assertEqual(len(calls), 1, "BM25 index chỉ được dựng 1 lần cho mọi mode")
        finally:
            ar.build_bm25_index = original

    def test_all_modes_use_same_corpus_and_question(self):
        result = self._compare()
        self.assertEqual(result["strategy"], "hierarchical")
        self.assertEqual(result["question"], "Điều 7 cơ cấu lại thời hạn trả nợ")


class RetrieveForModeTests(_AnswerTestBase):
    def test_retrieve_for_mode_never_generates(self):
        calls = []
        original = ar.generate_grounded_answer
        try:
            ar.generate_grounded_answer = lambda *a, **kw: calls.append(1)
            for mode in ar.VALID_MODES:
                ar.retrieve_for_mode(
                    "Điều 7", mode, self.config, "hierarchical",
                    chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
                    embed_client_factory=lambda k: _FakeClient(DIM, "query"),
                    rerank_scorer=_high_scorer,
                )
            self.assertEqual(calls, [])
        finally:
            ar.generate_grounded_answer = original

    def test_respects_final_top_k(self):
        for mode in ar.VALID_MODES:
            with self.subTest(mode=mode):
                out = ar.retrieve_for_mode(
                    "Điều 7", mode, self.config, "hierarchical",
                    chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
                    embed_client_factory=lambda k: _FakeClient(DIM, "query"),
                    rerank_scorer=_high_scorer,
                )
                self.assertLessEqual(len(out["candidates"]), self.config.final_top_k)


if __name__ == "__main__":
    unittest.main()
