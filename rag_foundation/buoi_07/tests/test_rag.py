"""tests/test_rag.py — Bộ test tự động cho Buổi 07 (Bước 08).

Chạy: <PYTHON> -m unittest tests.test_rag -v   (thực hiện từ thư mục buoi_07/)

Nguyên tắc bắt buộc (xem SPEC_buoi_07.md mục Testing):
  - Dùng `unittest` (không dùng pytest).
  - Không gọi Internet, không cần GEMINI_API_KEY thật — Gemini luôn được mock
    qua `client_factory` (dependency injection có sẵn trong rag.py).
  - Không đụng `storage/chroma/` thật — Chroma luôn dùng thư mục `tempfile`
    riêng cho mỗi test, xoá sạch ở `tearDown`.
  - Dữ liệu chunk dùng trong test đều là dữ liệu mô phỏng (không phải văn bản
    ngân hàng thật, không có thông tin khách hàng).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rag  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: Gemini giả lập (không gọi Internet)
# ---------------------------------------------------------------------------


def _deterministic_vector(text: str, dim: int, salt: str = "") -> list:
    h = hashlib.sha256((salt + text).encode("utf-8")).digest()
    return [((h[i % len(h)] / 255.0) - 0.5) + (i + 1) * 1e-6 for i in range(dim)]


class _FakeEmbeddingsResponse:
    def __init__(self, values):
        self.embeddings = [type("E", (), {"values": values})]


class _FakeModels:
    def __init__(self, dim, salt="doc", fail_after=None, bad_vector_at=None, gen_text=None, gen_raises=False):
        self.dim = dim
        self.salt = salt
        self.fail_after = fail_after
        self.bad_vector_at = bad_vector_at
        self.gen_text = gen_text
        self.gen_raises = gen_raises
        self.embed_calls = 0
        self.gen_calls = 0

    def embed_content(self, model, contents, config):
        self.embed_calls += 1
        if self.fail_after is not None and self.embed_calls > self.fail_after:
            raise RuntimeError(f"mô phỏng lỗi gọi API ở lần gọi thứ {self.embed_calls}")
        if self.bad_vector_at is not None and self.embed_calls == self.bad_vector_at:
            return _FakeEmbeddingsResponse([0.0] * self.dim)
        return _FakeEmbeddingsResponse(_deterministic_vector(contents, self.dim, salt=self.salt))

    def generate_content(self, model, contents):
        self.gen_calls += 1
        if self.gen_raises:
            raise RuntimeError("mô phỏng lỗi gọi Gemini generation")
        return type("R", (), {"text": self.gen_text})


class _FakeClient:
    def __init__(self, dim, **kwargs):
        self.models = _FakeModels(dim, **kwargs)


def _index_factory(dim):
    return lambda api_key: _FakeClient(dim, salt="doc")


def _query_factory(dim, **kwargs):
    return lambda api_key: _FakeClient(dim, salt="query", **kwargs)


def _write_env(path: Path, **overrides) -> Path:
    values = {
        "GEMINI_API_KEY": "fake-key",
        "GEMINI_EMBEDDING_MODEL": "gemini-embedding-2",
        "GEMINI_EMBEDDING_DIM": "128",
        "GEMINI_GENERATION_MODEL": "gemini-3.5-flash-lite",
        "DEFAULT_TOP_K": "3",
        "RAG_MAX_DISTANCE": "0.45",
    }
    values.update(overrides)
    lines = [f"{k}={v}" for k, v in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_chunks(dir_: Path, filename: str, records: list) -> None:
    (dir_ / filename).write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def _sample_records(n: int = 4, strategy: str = "hierarchical", source: str = "doc-a") -> list:
    return [
        {
            "chunk_id": f"c{i}",
            "strategy": strategy,
            "source": source,
            "page_start": i + 1,
            "page_end": i + 1,
            "text": f"noi dung mo phong so {i} ve nghiep vu tin dung ngan hang",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Data Contract — validate_chunk / load_chunks
# ---------------------------------------------------------------------------


class ValidateChunkTests(unittest.TestCase):
    def _base(self, **overrides) -> dict:
        record = {
            "chunk_id": "c1",
            "strategy": "hierarchical",
            "source": "doc-a",
            "page_start": 1,
            "page_end": 2,
            "text": "  noi dung  ",
        }
        record.update(overrides)
        return record

    def test_valid_record_passes_and_strips_text(self):
        result = rag.validate_chunk(self._base(), "f.json", 0)
        self.assertEqual(result["text"], "noi dung")
        self.assertEqual(result["strategy"], "hierarchical")

    def test_missing_required_field_raises(self):
        record = self._base()
        del record["source"]
        with self.assertRaises(rag.DataError):
            rag.validate_chunk(record, "f.json", 0)

    def test_wrong_type_fields_raise(self):
        for field in ("chunk_id", "strategy", "source", "text"):
            with self.subTest(field=field):
                record = self._base(**{field: 123})
                with self.assertRaises(rag.DataError):
                    rag.validate_chunk(record, "f.json", 0)

    def test_empty_string_after_strip_raises(self):
        for field in ("chunk_id", "strategy", "source"):
            with self.subTest(field=field):
                record = self._base(**{field: "   "})
                with self.assertRaises(rag.DataError):
                    rag.validate_chunk(record, "f.json", 0)

    def test_invalid_strategy_value_raises(self):
        with self.assertRaises(rag.DataError):
            rag.validate_chunk(self._base(strategy="khong_hop_le"), "f.json", 0)

    def test_fixed_size_alias_normalized_to_fixed_dash_size(self):
        result = rag.validate_chunk(self._base(strategy="fixed_size"), "f.json", 0)
        self.assertEqual(result["strategy"], "fixed-size")

    def test_page_boolean_rejected(self):
        for field in ("page_start", "page_end"):
            with self.subTest(field=field):
                with self.assertRaises(rag.DataError):
                    rag.validate_chunk(self._base(**{field: True}), "f.json", 0)

    def test_page_non_int_rejected(self):
        with self.assertRaises(rag.DataError):
            rag.validate_chunk(self._base(page_start=1.5), "f.json", 0)

    def test_page_less_than_one_rejected(self):
        with self.assertRaises(rag.DataError):
            rag.validate_chunk(self._base(page_start=0), "f.json", 0)

    def test_page_start_greater_than_page_end_rejected(self):
        with self.assertRaises(rag.DataError):
            rag.validate_chunk(self._base(page_start=5, page_end=2), "f.json", 0)

    def test_does_not_mutate_source_record(self):
        record = self._base()
        original_text = record["text"]
        rag.validate_chunk(record, "f.json", 0)
        self.assertEqual(record["text"], original_text)

    def test_error_message_includes_file_and_position(self):
        record = self._base()
        del record["source"]
        with self.assertRaises(rag.DataError) as ctx:
            rag.validate_chunk(record, "myfile.json", 3)
        self.assertIn("myfile.json", str(ctx.exception))
        self.assertIn("3", str(ctx.exception))


class LoadChunksTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_missing_directory_raises(self):
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir / "khong_ton_tai", strategy="hierarchical")

    def test_no_json_files_raises(self):
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir, strategy="hierarchical")

    def test_invalid_json_raises(self):
        (self.dir / "bad.json").write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir, strategy="hierarchical")

    def test_invalid_top_level_structure_raises(self):
        (self.dir / "bad.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir, strategy="hierarchical")

    def test_record_not_object_raises(self):
        (self.dir / "bad.json").write_text(json.dumps(["chuoi", 123]), encoding="utf-8")
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir, strategy="hierarchical")

    def test_object_with_chunks_field_accepted(self):
        _write_chunks(self.dir, "a.json", [])
        (self.dir / "a.json").write_text(
            json.dumps({"chunks": _sample_records(2)}), encoding="utf-8"
        )
        chunks, stats = rag.load_chunks(input_dir=self.dir, strategy="hierarchical")
        self.assertEqual(stats["valid_chunks"], 2)

    def test_duplicate_chunk_id_raises(self):
        records = [
            {"chunk_id": "same", "strategy": "hierarchical", "source": "s", "page_start": 1, "page_end": 1, "text": "a"},
            {"chunk_id": "same", "strategy": "hierarchical", "source": "s", "page_start": 2, "page_end": 2, "text": "b"},
        ]
        _write_chunks(self.dir, "dup.json", records)
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir, strategy="hierarchical")

    def test_empty_text_skipped_not_failed(self):
        records = [
            {"chunk_id": "e1", "strategy": "hierarchical", "source": "s", "page_start": 1, "page_end": 1, "text": "   "},
            {"chunk_id": "e2", "strategy": "hierarchical", "source": "s", "page_start": 1, "page_end": 1, "text": "noi dung that"},
        ]
        _write_chunks(self.dir, "e.json", records)
        chunks, stats = rag.load_chunks(input_dir=self.dir, strategy="hierarchical")
        self.assertEqual(stats["empty_text_skipped"], 1)
        self.assertEqual(stats["valid_chunks"], 1)
        self.assertEqual(chunks[0]["chunk_id"], "e2")

    def test_invalid_strategy_argument_raises(self):
        with self.assertRaises(rag.DataError):
            rag.load_chunks(input_dir=self.dir, strategy="khong_hop_le")

    def test_fixed_size_alias_filters_correctly(self):
        _write_chunks(self.dir, "a.json", _sample_records(3, strategy="fixed_size"))
        chunks, stats = rag.load_chunks(input_dir=self.dir, strategy="fixed-size")
        self.assertEqual(stats["valid_chunks"], 3)
        self.assertTrue(all(c["strategy"] == "fixed-size" for c in chunks))

    def test_stats_fields_correct_with_mixed_strategies(self):
        records = _sample_records(2, strategy="hierarchical") + _sample_records(3, strategy="semantic")
        _write_chunks(self.dir, "mixed.json", records)
        chunks, stats = rag.load_chunks(input_dir=self.dir, strategy="hierarchical")
        self.assertEqual(stats["total_records"], 5)
        self.assertEqual(stats["selected_records"], 2)
        self.assertEqual(stats["valid_chunks"], 2)

    def test_fixture_file_loads_all_three_strategies(self):
        fixture_dir = Path(__file__).resolve().parent / "fixtures"
        for strategy, expected in (("hierarchical", 3), ("semantic", 1), ("fixed-size", 1)):
            with self.subTest(strategy=strategy):
                chunks, stats = rag.load_chunks(input_dir=fixture_dir, strategy=strategy)
                self.assertEqual(stats["valid_chunks"], expected)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class LoadConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_valid_config_parsed_correctly(self):
        env = _write_env(self.dir / ".env")
        config = rag.load_config(env)
        self.assertEqual(config.embedding_dim, 128)
        self.assertEqual(config.default_top_k, 3)
        self.assertEqual(config.max_distance, 0.45)

    def test_missing_embedding_model_raises(self):
        env = _write_env(self.dir / ".env", GEMINI_EMBEDDING_MODEL="")
        with self.assertRaises(rag.ConfigError):
            rag.load_config(env)

    def test_missing_generation_model_raises(self):
        env = _write_env(self.dir / ".env", GEMINI_GENERATION_MODEL="")
        with self.assertRaises(rag.ConfigError):
            rag.load_config(env)

    def test_dim_not_integer_raises(self):
        env = _write_env(self.dir / ".env", GEMINI_EMBEDDING_DIM="abc")
        with self.assertRaises(rag.ConfigError):
            rag.load_config(env)

    def test_dim_out_of_range_raises(self):
        env = _write_env(self.dir / ".env", GEMINI_EMBEDDING_DIM="5000")
        with self.assertRaises(rag.ConfigError):
            rag.load_config(env)

    def test_top_k_out_of_range_raises(self):
        env = _write_env(self.dir / ".env", DEFAULT_TOP_K="0")
        with self.assertRaises(rag.ConfigError):
            rag.load_config(env)

    def test_negative_max_distance_raises(self):
        env = _write_env(self.dir / ".env", RAG_MAX_DISTANCE="-1")
        with self.assertRaises(rag.ConfigError):
            rag.load_config(env)

    def test_empty_api_key_allowed(self):
        env = _write_env(self.dir / ".env", GEMINI_API_KEY="")
        config = rag.load_config(env)
        self.assertEqual(config.gemini_api_key, "")

    def test_reload_overrides_previous_process_env(self):
        env1 = _write_env(self.dir / "a.env", GEMINI_API_KEY="key-mot")
        cfg1 = rag.load_config(env1)
        self.assertEqual(cfg1.gemini_api_key, "key-mot")
        env2 = _write_env(self.dir / "b.env", GEMINI_API_KEY="")
        cfg2 = rag.load_config(env2)
        self.assertEqual(cfg2.gemini_api_key, "", "load_config lần sau phải ghi đè env var, không giữ giá trị cũ")


# ---------------------------------------------------------------------------
# Index Contract — validate_embeddings / collection_name
# ---------------------------------------------------------------------------


class ValidateEmbeddingsTests(unittest.TestCase):
    def test_count_mismatch_raises(self):
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings([[0.1] * 8], expected_count=2, expected_dim=8)

    def test_not_a_list_raises(self):
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings(["khong phai list"], expected_count=1, expected_dim=8)

    def test_wrong_dimension_raises(self):
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings([[0.1] * 4], expected_count=1, expected_dim=8)

    def test_boolean_element_raises(self):
        v = [0.1] * 8
        v[2] = True
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings([v], expected_count=1, expected_dim=8)

    def test_nan_element_raises(self):
        v = [0.1] * 8
        v[2] = float("nan")
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings([v], expected_count=1, expected_dim=8)

    def test_infinity_element_raises(self):
        v = [0.1] * 8
        v[2] = float("inf")
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings([v], expected_count=1, expected_dim=8)

    def test_zero_vector_raises(self):
        with self.assertRaises(rag.EmbeddingError):
            rag.validate_embeddings([[0.0] * 8], expected_count=1, expected_dim=8)

    def test_valid_vectors_pass(self):
        vectors = [[0.1 + i * 0.01] * 8 for i in range(3)]
        rag.validate_embeddings(vectors, expected_count=3, expected_dim=8)  # không raise


class CollectionNameTests(unittest.TestCase):
    def test_deterministic(self):
        a = rag.collection_name("hierarchical", 768, "gemini-embedding-2")
        b = rag.collection_name("hierarchical", 768, "gemini-embedding-2")
        self.assertEqual(a, b)

    def test_differs_by_model_strategy_dim(self):
        base = rag.collection_name("hierarchical", 768, "gemini-embedding-2")
        self.assertNotEqual(base, rag.collection_name("hierarchical", 768, "gemini-embedding-3"))
        self.assertNotEqual(base, rag.collection_name("semantic", 768, "gemini-embedding-2"))
        self.assertNotEqual(base, rag.collection_name("hierarchical", 1024, "gemini-embedding-2"))

    def test_format_includes_strategy_dim_and_hash(self):
        name = rag.collection_name("hierarchical", 768, "gemini-embedding-2")
        self.assertTrue(name.startswith("nhnn-hierarchical-768-"))
        self.assertEqual(len(name.split("-")[-1]), 8)


# ---------------------------------------------------------------------------
# Index Contract — index_chunks / get_status (Chroma qua tempfile, không đụng
# storage/chroma/ thật)
# ---------------------------------------------------------------------------


class IndexChunksTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chunks_dir = self.work / "chunks"
        self.chunks_dir.mkdir()
        self.chroma_dir = self.work / "chroma"
        self.config = rag.load_config(_write_env(self.work / ".env"))
        _write_chunks(self.chunks_dir, "part1.json", _sample_records(5))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_status_before_index_no_collection_created(self):
        status = rag.get_status("hierarchical", self.config, persist_path=self.chroma_dir)
        self.assertFalse(status["collection_exists"])
        self.assertEqual(status["record_count"], 0)

    def test_index_first_run_indexes_all_chunks(self):
        result = rag.index_chunks(
            "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )
        self.assertEqual(result["chunks_embedded"], 5)
        self.assertEqual(result["record_count"], 5)

    def test_index_idempotent_second_run_same_count(self):
        for _ in range(2):
            result = rag.index_chunks(
                "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
                client_factory=_index_factory(128),
            )
        self.assertEqual(result["record_count"], 5)

    def test_index_with_reset_recreates_collection(self):
        rag.index_chunks(
            "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )
        result = rag.index_chunks(
            "hierarchical", self.config, reset=True, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )
        self.assertTrue(result["reset"])
        self.assertEqual(result["record_count"], 5)

    def test_index_embedding_failure_keeps_existing_collection_even_with_reset(self):
        rag.index_chunks(
            "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )
        before = rag.get_status("hierarchical", self.config, persist_path=self.chroma_dir)

        with self.assertRaises(rag.EmbeddingError):
            rag.index_chunks(
                "hierarchical", self.config, reset=True, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
                client_factory=lambda api_key: _FakeClient(128, salt="doc", fail_after=2),
            )

        after = rag.get_status("hierarchical", self.config, persist_path=self.chroma_dir)
        self.assertTrue(after["collection_exists"])
        self.assertEqual(after["record_count"], before["record_count"])

    def test_index_zero_vector_blocks_before_upsert(self):
        with self.assertRaises(rag.EmbeddingError):
            rag.index_chunks(
                "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
                client_factory=lambda api_key: _FakeClient(128, salt="doc", bad_vector_at=3),
            )
        status = rag.get_status("hierarchical", self.config, persist_path=self.chroma_dir)
        self.assertFalse(status["collection_exists"])

    def test_index_metadata_mismatch_blocked_without_reset(self):
        import chromadb

        raw = chromadb.PersistentClient(path=str(self.chroma_dir))
        name = rag.collection_name("hierarchical", self.config.embedding_dim, self.config.embedding_model)
        raw.get_or_create_collection(
            name=name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={
                "strategy": "hierarchical",
                "embedding_model": self.config.embedding_model,
                "embedding_dim": self.config.embedding_dim,
                "distance_metric": "cosine",
                "schema_version": 0,  # cố tình sai
            },
        )
        with self.assertRaises(rag.ChromaError):
            rag.index_chunks(
                "hierarchical", self.config, reset=False, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
                client_factory=_index_factory(128),
            )

    def test_index_metadata_mismatch_resolved_with_reset(self):
        import chromadb

        raw = chromadb.PersistentClient(path=str(self.chroma_dir))
        name = rag.collection_name("hierarchical", self.config.embedding_dim, self.config.embedding_model)
        raw.get_or_create_collection(
            name=name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={
                "strategy": "hierarchical",
                "embedding_model": self.config.embedding_model,
                "embedding_dim": self.config.embedding_dim,
                "distance_metric": "cosine",
                "schema_version": 0,
            },
        )
        result = rag.index_chunks(
            "hierarchical", self.config, reset=True, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )
        self.assertEqual(result["record_count"], 5)

    def test_index_without_api_key_raises_no_fake_vectors(self):
        nokey = rag.load_config(_write_env(self.work / "nokey.env", GEMINI_API_KEY=""))
        with self.assertRaises(rag.EmbeddingError):
            rag.index_chunks(
                "hierarchical", nokey, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
                client_factory=_index_factory(128),
            )
        status = rag.get_status("hierarchical", nokey, persist_path=self.chroma_dir)
        self.assertFalse(status["collection_exists"])

    def test_index_no_valid_chunks_raises(self):
        empty_dir = self.work / "empty_chunks"
        empty_dir.mkdir()
        _write_chunks(empty_dir, "only_other_strategy.json", _sample_records(2, strategy="semantic"))
        with self.assertRaises(rag.DataError):
            rag.index_chunks(
                "hierarchical", self.config, chunks_dir=empty_dir, persist_path=self.chroma_dir,
                client_factory=_index_factory(128),
            )


# ---------------------------------------------------------------------------
# Retrieval Contract
# ---------------------------------------------------------------------------


class RetrieveTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chunks_dir = self.work / "chunks"
        self.chunks_dir.mkdir()
        self.chroma_dir = self.work / "chroma"
        self.config = rag.load_config(_write_env(self.work / ".env"))
        _write_chunks(self.chunks_dir, "part1.json", _sample_records(4))
        rag.index_chunks(
            "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_empty_question_raises(self):
        with self.assertRaises(rag.DataError):
            rag.retrieve("   ", "hierarchical", self.config, persist_path=self.chroma_dir, client_factory=_query_factory(128))

    def test_missing_collection_raises(self):
        with self.assertRaises(rag.ChromaError):
            rag.retrieve("cau hoi", "semantic", self.config, persist_path=self.chroma_dir, client_factory=_query_factory(128))

    def test_returns_top_k_evidence_with_distance_and_real_metadata(self):
        evidence = rag.retrieve(
            "cau hoi ve tin dung", "hierarchical", self.config, top_k=3, persist_path=self.chroma_dir,
            client_factory=_query_factory(128),
        )
        self.assertEqual(len(evidence), 3)
        self.assertEqual([e["label"] for e in evidence], ["E1", "E2", "E3"])
        self.assertTrue(all(isinstance(e["distance"], float) for e in evidence))
        self.assertTrue(all(e["chunk_id"].startswith("c") for e in evidence))
        self.assertTrue(all(e["source"] == "doc-a" for e in evidence))

    def test_default_top_k_used_when_not_specified(self):
        evidence = rag.retrieve(
            "cau hoi", "hierarchical", self.config, persist_path=self.chroma_dir, client_factory=_query_factory(128)
        )
        self.assertEqual(len(evidence), self.config.default_top_k)


# ---------------------------------------------------------------------------
# Citation Contract — ask() end-to-end
# ---------------------------------------------------------------------------


class AskTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chunks_dir = self.work / "chunks"
        self.chunks_dir.mkdir()
        self.chroma_dir = self.work / "chroma"
        self.config = rag.load_config(_write_env(self.work / ".env"))
        _write_chunks(self.chunks_dir, "part1.json", _sample_records(4))
        rag.index_chunks(
            "hierarchical", self.config, chunks_dir=self.chunks_dir, persist_path=self.chroma_dir,
            client_factory=_index_factory(128),
        )
        # vector giả lập không mang ngữ nghĩa thật -> distance cosine ~1.0 giữa
        # câu hỏi và tài liệu; dùng ngưỡng nới lỏng cho các test cần evidence
        # "đạt", còn test insufficient_evidence dùng đúng config mặc định.
        self.lenient_config = rag.Config(**{**self.config.__dict__, "max_distance": 2.0})

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_ask_returns_required_fields(self):
        result = rag.ask(
            "cau hoi", "hierarchical", self.lenient_config, top_k=3, persist_path=self.chroma_dir,
            embed_client_factory=_query_factory(128), generation_client_factory=_query_factory(128, gen_text="tra loi [E1]"),
        )
        for field in ("status", "answer", "evidence", "citations", "warnings", "collection", "strategy", "top_k"):
            self.assertIn(field, result)

    def test_ask_insufficient_evidence_skips_generation(self):
        result = rag.ask(
            "cau hoi", "hierarchical", self.config, top_k=3, persist_path=self.chroma_dir,
            embed_client_factory=_query_factory(128), generation_client_factory=_query_factory(128, gen_text="khong duoc goi"),
        )
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["citations"], [])

    def test_ask_answered_maps_valid_citation_to_real_metadata(self):
        result = rag.ask(
            "cau hoi", "hierarchical", self.lenient_config, top_k=3, persist_path=self.chroma_dir,
            embed_client_factory=_query_factory(128), generation_client_factory=_query_factory(128, gen_text="tra loi co can cu [E1]."),
        )
        self.assertEqual(result["status"], "answered")
        self.assertIn("[E1]", result["answer"])
        self.assertTrue(any(c["label"] == "E1" and c["source"] == "doc-a" for c in result["citations"]))

    def test_ask_strips_invalid_citation_label_and_warns(self):
        result = rag.ask(
            "cau hoi", "hierarchical", self.lenient_config, top_k=3, persist_path=self.chroma_dir,
            embed_client_factory=_query_factory(128),
            generation_client_factory=_query_factory(128, gen_text="tra loi dung [E1] va sai [E99]."),
        )
        self.assertNotIn("[E99]", result["answer"])
        self.assertTrue(any("E99" in w for w in result["warnings"]))
        self.assertFalse(any(c["label"] == "E99" for c in result["citations"]))

    def test_ask_retrieval_only_when_generation_raises(self):
        result = rag.ask(
            "cau hoi", "hierarchical", self.lenient_config, top_k=3, persist_path=self.chroma_dir,
            embed_client_factory=_query_factory(128), generation_client_factory=_query_factory(128, gen_raises=True),
        )
        self.assertEqual(result["status"], "retrieval_only")
        self.assertIsNone(result["answer"])
        self.assertTrue(len(result["evidence"]) > 0)

    def test_ask_retrieval_only_when_generation_returns_empty(self):
        result = rag.ask(
            "cau hoi", "hierarchical", self.lenient_config, top_k=3, persist_path=self.chroma_dir,
            embed_client_factory=_query_factory(128), generation_client_factory=_query_factory(128, gen_text=""),
        )
        self.assertEqual(result["status"], "retrieval_only")

    def test_generate_answer_without_key_raises(self):
        nokey = rag.Config(**{**self.config.__dict__, "gemini_api_key": ""})
        with self.assertRaises(rag.EmbeddingError):
            rag.generate_answer(
                "cau hoi",
                [{"label": "E1", "source": "s", "page_start": 1, "page_end": 1, "text": "t"}],
                nokey,
            )


# ---------------------------------------------------------------------------
# Security — thông báo lỗi không được lộ giá trị API key
# ---------------------------------------------------------------------------


class SecurityTests(unittest.TestCase):
    def test_embedding_error_does_not_leak_api_key_value(self):
        secret = "SUPER-SECRET-KEY-KHONG-DUOC-LO"
        config = rag.Config(
            gemini_api_key=secret,
            embedding_model="gemini-embedding-2",
            embedding_dim=8,
            generation_model="gemini-3.5-flash-lite",
            default_top_k=3,
            max_distance=0.45,
        )

        def _raising_factory(api_key):
            raise RuntimeError("401 Unauthorized")

        with self.assertRaises(rag.EmbeddingError) as ctx:
            rag.embed_documents(
                [{"chunk_id": "c1", "source": "s", "text": "t"}], config, client_factory=_raising_factory
            )
        self.assertNotIn(secret, str(ctx.exception))

    def test_config_error_does_not_echo_api_key(self):
        work = Path(tempfile.mkdtemp())
        try:
            secret = "SUPER-SECRET-KEY-2"
            env = _write_env(work / ".env", GEMINI_API_KEY=secret, GEMINI_EMBEDDING_DIM="99999")
            with self.assertRaises(rag.ConfigError) as ctx:
                rag.load_config(env)
            self.assertNotIn(secret, str(ctx.exception))
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI — validate (đường duy nhất không cần config/key nên test được trực tiếp)
# ---------------------------------------------------------------------------


class CLIValidateTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_cmd_validate_success_returns_zero(self):
        _write_chunks(self.dir, "a.json", _sample_records(3))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rag._cmd_validate("hierarchical", input_dir=self.dir)
        self.assertEqual(code, 0)
        self.assertIn("valid_chunks: 3", buf.getvalue())

    def test_cmd_validate_failure_returns_one(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rag._cmd_validate("hierarchical", input_dir=self.dir / "khong_ton_tai")
        self.assertEqual(code, 1)
        self.assertIn("[LỖI]", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
