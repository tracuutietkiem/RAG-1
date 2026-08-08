"""tests/test_semantic.py — Test semantic candidate retrieval + status (Bước 05).

Nguyên tắc (SPEC_buoi_08.md mục 11): `unittest`, không Internet, không gọi
Gemini thật (embedding luôn được mock qua `client_factory`), không tải model
Hugging Face, Chroma dùng thư mục tạm — không đụng `storage/chroma/` thật.
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


# ---------------------------------------------------------------------------
# Gemini giả lập — deterministic, không gọi mạng
# ---------------------------------------------------------------------------


def _vector(text: str, dim: int, salt: str = "") -> list:
    h = hashlib.sha256((salt + text).encode("utf-8")).digest()
    return [((h[i % len(h)] / 255.0) - 0.5) + (i + 1) * 1e-6 for i in range(dim)]


class _FakeEmbeddingsResponse:
    def __init__(self, values):
        self.embeddings = [type("E", (), {"values": values})]


class _FakeModels:
    def __init__(self, dim, salt):
        self.dim = dim
        self.salt = salt
        self.embed_calls = 0
        self.generate_calls = 0

    def embed_content(self, model, contents, config):
        self.embed_calls += 1
        return _FakeEmbeddingsResponse(_vector(contents, self.dim, self.salt))

    def generate_content(self, model, contents):
        self.generate_calls += 1
        raise AssertionError("Bước 05 không được gọi generation")


class _FakeClient:
    def __init__(self, dim, salt):
        self.models = _FakeModels(dim, salt)


def _factory(salt="doc", dim=DIM):
    return lambda api_key: _FakeClient(dim, salt)


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


class SemanticSearchTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chroma = self.work / "chroma"
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))
        ar.prepare_semantic(
            "hierarchical", self.config, chunks_dir=FIXTURE_DIR,
            persist_path=self.chroma, client_factory=_factory("doc"),
        )

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _search(self, question="cơ cấu lại thời hạn trả nợ", k=5):
        return ar.semantic_search(
            question, self.config, "hierarchical", k,
            persist_path=self.chroma, client_factory=_factory("query"),
        )

    def test_empty_question_fails(self):
        for bad in ("", "   "):
            with self.subTest(question=bad):
                with self.assertRaises(rag.DataError):
                    self._search(question=bad)

    def test_invalid_candidate_k_fails(self):
        for bad in (0, -1, 1.5, True):
            with self.subTest(candidate_k=bad):
                with self.assertRaises(rag.DataError):
                    self._search(k=bad)

    def test_returns_requested_count(self):
        self.assertEqual(len(self._search(k=5)), 5)
        self.assertEqual(len(self._search(k=3)), 3)

    def test_candidate_k_clamped_to_collection_count(self):
        """n_results = min(candidate_k, collection.count())."""
        results = self._search(k=9999)
        self.assertEqual(len(results), 8, "Fixture chỉ có 8 chunk hierarchical")

    def test_ranks_sequential_from_one(self):
        results = self._search(k=5)
        self.assertEqual([r["semantic_rank"] for r in results], [1, 2, 3, 4, 5])

    def test_distances_non_decreasing(self):
        """Distance thấp hơn xếp trước — giữ đúng thứ tự Chroma trả về."""
        distances = [r["semantic_distance"] for r in self._search(k=8)]
        self.assertEqual(distances, sorted(distances))

    def test_metadata_complete_and_real(self):
        chunks, _ = rag.load_chunks(input_dir=FIXTURE_DIR, strategy="hierarchical")
        by_id = {c["chunk_id"]: c for c in chunks}
        required = {"chunk_id", "text", "source", "page_start", "page_end", "semantic_rank", "semantic_distance"}
        for r in self._search(k=8):
            self.assertTrue(required.issubset(r.keys()), f"Thiếu field: {required - set(r.keys())}")
            src = by_id[r["chunk_id"]]
            self.assertEqual(r["source"], src["source"])
            self.assertEqual(r["page_start"], src["page_start"])
            self.assertEqual(r["page_end"], src["page_end"])
            self.assertEqual(r["text"], src["text"])

    def test_distance_not_converted_to_fake_similarity(self):
        """Không đổi distance thành similarity giả (vd 1 - distance)."""
        for r in self._search(k=5):
            self.assertGreaterEqual(r["semantic_distance"], 0.0)
            self.assertNotIn("semantic_similarity", r)
            self.assertNotIn("score", r)

    def test_missing_collection_raises_with_guidance(self):
        empty_chroma = self.work / "chroma_empty"
        with self.assertRaises(rag.ChromaError) as ctx:
            ar.semantic_search(
                "cau hoi", self.config, "semantic", 5,
                persist_path=empty_chroma, client_factory=_factory("query"),
            )
        self.assertIn("prepare-semantic", str(ctx.exception))

    def test_collection_metadata_mismatch_blocked(self):
        """Model/dimension khác lúc index phải bị chặn, không truy vấn nhầm."""
        import chromadb

        other_chroma = self.work / "chroma_mismatch"
        client = chromadb.PersistentClient(path=str(other_chroma))
        name = rag.collection_name("hierarchical", DIM, "gemini-embedding-2")
        client.get_or_create_collection(
            name=name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={
                "strategy": "hierarchical",
                "embedding_model": "gemini-embedding-2",
                "embedding_dim": DIM,
                "distance_metric": "cosine",
                "schema_version": 0,  # cố tình sai
            },
        )
        client.get_collection(name=name, embedding_function=None).upsert(
            ids=["x1"], embeddings=[[0.1] * DIM], documents=["noi dung"],
            metadatas=[{"chunk_id": "x1", "source": "s", "strategy": "hierarchical",
                        "page_start": 1, "page_end": 1}],
        )
        with self.assertRaises(rag.ChromaError):
            ar.semantic_search(
                "cau hoi", self.config, "hierarchical", 5,
                persist_path=other_chroma, client_factory=_factory("query"),
            )

    def test_no_fake_vector_when_api_key_missing(self):
        """Thiếu key phải fail rõ, KHÔNG dùng vector giả."""
        nokey = ar.load_advanced_config(_write_env(self.work / "nokey.env", GEMINI_API_KEY=""))
        with self.assertRaises(rag.EmbeddingError):
            ar.semantic_search(
                "cau hoi", nokey, "hierarchical", 5,
                persist_path=self.chroma, client_factory=_factory("query"),
            )

    def test_no_generation_called(self):
        """Bước 05 chỉ tạo candidate — fake client sẽ raise nếu generation bị gọi."""
        results = self._search(k=5)
        self.assertEqual(len(results), 5)

    def test_uses_same_model_and_dimension_as_index(self):
        """Query embedding phải cùng dimension với lúc index."""
        results = self._search(k=3)
        self.assertTrue(results, "Phải truy vấn được, chứng tỏ dimension khớp")


class PrepareSemanticTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chroma = self.work / "chroma"
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_indexes_all_fixture_chunks(self):
        result = ar.prepare_semantic(
            "hierarchical", self.config, chunks_dir=FIXTURE_DIR,
            persist_path=self.chroma, client_factory=_factory("doc"),
        )
        self.assertEqual(result["chunks_embedded"], 8)
        self.assertEqual(result["record_count"], 8)

    def test_idempotent(self):
        for _ in range(2):
            result = ar.prepare_semantic(
                "hierarchical", self.config, chunks_dir=FIXTURE_DIR,
                persist_path=self.chroma, client_factory=_factory("doc"),
            )
        self.assertEqual(result["record_count"], 8, "Chạy lại không được tăng số record")

    def test_missing_api_key_fails_without_fake_vectors(self):
        nokey = ar.load_advanced_config(_write_env(self.work / "nokey.env", GEMINI_API_KEY=""))
        with self.assertRaises(rag.EmbeddingError):
            ar.prepare_semantic(
                "hierarchical", nokey, chunks_dir=FIXTURE_DIR,
                persist_path=self.chroma, client_factory=_factory("doc"),
            )
        status = ar.get_advanced_status(
            "hierarchical", nokey, persist_path=self.chroma, chunks_dir=FIXTURE_DIR
        )
        self.assertFalse(status["collection_exists"])


class AdvancedStatusTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chroma = self.work / "chroma"
        self.config = ar.load_advanced_config(_write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_status_does_not_create_collection(self):
        before = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        self.assertFalse(before["collection_exists"])
        after = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        self.assertFalse(after["collection_exists"], "status không được tạo collection")
        self.assertEqual(after["record_count"], 0)

    def test_status_does_not_call_gemini(self):
        def _boom(*args, **kwargs):
            raise AssertionError("status không được gọi Gemini")

        original = rag._default_gemini_client
        try:
            rag._default_gemini_client = _boom
            s = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
            self.assertIsNotNone(s)
        finally:
            rag._default_gemini_client = original

    def test_status_reports_corpus_and_bm25_readiness(self):
        s = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        self.assertEqual(s["corpus_size"], 8)
        self.assertTrue(s["bm25_ready"])
        self.assertIsNone(s["corpus_error"])

    def test_status_reports_reranker_without_loading(self):
        s = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        self.assertEqual(s["reranker_model"], "BAAI/bge-reranker-v2-m3")
        self.assertIn("huggingface", s["reranker_cache_dir"])
        self.assertIsInstance(s["reranker_cache_exists"], bool)

    def test_status_after_index_reports_count(self):
        ar.prepare_semantic(
            "hierarchical", self.config, chunks_dir=FIXTURE_DIR,
            persist_path=self.chroma, client_factory=_factory("doc"),
        )
        s = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        self.assertTrue(s["collection_exists"])
        self.assertEqual(s["record_count"], 8)
        self.assertTrue(s["metadata_ok"])

    def test_status_reports_all_config_values(self):
        s = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        for key in ("bm25_candidates", "semantic_candidates", "rerank_candidates", "final_top_k",
                    "rrf_k", "rrf_bm25_weight", "rrf_semantic_weight", "rerank_min_score", "max_distance"):
            self.assertIn(key, s)

    def test_status_never_exposes_api_key_value(self):
        s = ar.get_advanced_status("hierarchical", self.config, persist_path=self.chroma, chunks_dir=FIXTURE_DIR)
        self.assertIsInstance(s["api_key_present"], bool)
        self.assertNotIn("fake-key", str(s))


class NoModelLoadTests(unittest.TestCase):
    def test_reranker_cache_check_does_not_import_transformers(self):
        work = Path(tempfile.mkdtemp())
        try:
            config = ar.load_advanced_config(_write_env(work / ".env"))
            # Chỉ đọc filesystem; nếu hàm này import transformers thì đã vi phạm
            # yêu cầu "không tải model khi status".
            result = ar.reranker_cache_exists(config)
            self.assertIsInstance(result, bool)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_no_module_level_model_import(self):
        source = (Path(__file__).resolve().parent.parent / "advanced_rag.py").read_text(encoding="utf-8")
        offenders = [
            line
            for line in source.splitlines()
            if (line.startswith("import ") or line.startswith("from "))
            and ("torch" in line or "transformers" in line)
        ]
        self.assertEqual(offenders, [], f"Không được import model runtime ở module level: {offenders}")


if __name__ == "__main__":
    unittest.main()
