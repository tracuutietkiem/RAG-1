"""tests/test_rrf.py — Test Reciprocal Rank Fusion và hybrid search (Bước 06).

Nguyên tắc (SPEC_buoi_08.md mục 11): `unittest`, offline hoàn toàn. Các test
công thức RRF dùng số nhỏ tính tay được để chứng minh đúng số học.
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


def _bm25_cand(chunk_id, rank, score, text=None, source="s.pdf", p1=1, p2=1):
    return {
        "chunk_id": chunk_id,
        "text": text if text is not None else f"noi dung {chunk_id}",
        "source": source,
        "page_start": p1,
        "page_end": p2,
        "bm25_rank": rank,
        "bm25_score": score,
    }


def _sem_cand(chunk_id, rank, distance, text=None, source="s.pdf", p1=1, p2=1):
    return {
        "chunk_id": chunk_id,
        "text": text if text is not None else f"noi dung {chunk_id}",
        "source": source,
        "page_start": p1,
        "page_end": p2,
        "semantic_rank": rank,
        "semantic_distance": distance,
    }


class RRFFormulaTests(unittest.TestCase):
    def test_formula_both_branches_hand_computed(self):
        """
        rrf_k=60, weight=1.0 cả hai nhánh.
        c1: bm25_rank=1, semantic_rank=2 -> 1/61 + 1/62 = 0.0163934... + 0.0161290... = 0.0325225...
        """
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 9.9)], [_sem_cand("c1", 2, 0.2)], 60, 1.0, 1.0
        )
        expected = 1.0 / 61 + 1.0 / 62
        self.assertEqual(len(fused), 1)
        self.assertAlmostEqual(fused[0]["rrf_score"], expected, places=12)
        self.assertAlmostEqual(expected, 0.03252246, places=7)

    def test_formula_bm25_only(self):
        fused = ar.reciprocal_rank_fusion([_bm25_cand("c1", 3, 5.0)], [], 60, 1.0, 1.0)
        self.assertAlmostEqual(fused[0]["rrf_score"], 1.0 / 63, places=12)

    def test_formula_semantic_only(self):
        fused = ar.reciprocal_rank_fusion([], [_sem_cand("c1", 5, 0.3)], 60, 1.0, 1.0)
        self.assertAlmostEqual(fused[0]["rrf_score"], 1.0 / 65, places=12)

    def test_weights_applied(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 9.9)], [_sem_cand("c1", 1, 0.1)], 60, 2.0, 0.5
        )
        self.assertAlmostEqual(fused[0]["rrf_score"], 2.0 / 61 + 0.5 / 61, places=12)

    def test_bm25_weight_zero_removes_that_contribution(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 9.9)], [_sem_cand("c1", 4, 0.4)], 60, 0.0, 1.0
        )
        self.assertAlmostEqual(fused[0]["rrf_score"], 1.0 / 64, places=12)

    def test_semantic_weight_zero_removes_that_contribution(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 2, 9.9)], [_sem_cand("c1", 1, 0.1)], 60, 1.0, 0.0
        )
        self.assertAlmostEqual(fused[0]["rrf_score"], 1.0 / 62, places=12)

    def test_rrf_k_affects_score(self):
        low_k = ar.reciprocal_rank_fusion([_bm25_cand("c1", 1, 1.0)], [], 10, 1.0, 1.0)
        high_k = ar.reciprocal_rank_fusion([_bm25_cand("c1", 1, 1.0)], [], 100, 1.0, 1.0)
        self.assertAlmostEqual(low_k[0]["rrf_score"], 1.0 / 11, places=12)
        self.assertAlmostEqual(high_k[0]["rrf_score"], 1.0 / 101, places=12)

    def test_raw_scores_not_used_in_formula(self):
        """BM25 score / cosine distance khác nhau hoàn toàn nhưng cùng rank -> cùng rrf_score."""
        a = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 0.001)], [_sem_cand("c1", 1, 1.99)], 60, 1.0, 1.0
        )
        b = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 999.0)], [_sem_cand("c1", 1, 0.001)], 60, 1.0, 1.0
        )
        self.assertAlmostEqual(a[0]["rrf_score"], b[0]["rrf_score"], places=12)

    def test_invalid_rrf_k_raises(self):
        for bad in (0, -1, 1.5, True):
            with self.subTest(rrf_k=bad):
                with self.assertRaises(rag.DataError):
                    ar.reciprocal_rank_fusion([_bm25_cand("c1", 1, 1.0)], [], bad, 1.0, 1.0)

    def test_negative_weight_raises(self):
        with self.assertRaises(rag.DataError):
            ar.reciprocal_rank_fusion([_bm25_cand("c1", 1, 1.0)], [], 60, -1.0, 1.0)


class RRFUnionTests(unittest.TestCase):
    def test_overlap_not_duplicated(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 5.0), _bm25_cand("c2", 2, 4.0)],
            [_sem_cand("c1", 1, 0.1), _sem_cand("c3", 2, 0.2)],
            60, 1.0, 1.0,
        )
        ids = [c["chunk_id"] for c in fused]
        self.assertEqual(sorted(ids), ["c1", "c2", "c3"])
        self.assertEqual(len(ids), len(set(ids)), "Không được duplicate chunk_id")

    def test_bm25_only_candidate_kept(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("only_bm25", 1, 5.0)], [_sem_cand("other", 1, 0.1)], 60, 1.0, 1.0
        )
        entry = next(c for c in fused if c["chunk_id"] == "only_bm25")
        self.assertEqual(entry["matched_by"], ["bm25"])
        self.assertIsNone(entry["semantic_rank"])
        self.assertIsNone(entry["semantic_distance"])

    def test_semantic_only_candidate_kept(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("other", 1, 5.0)], [_sem_cand("only_sem", 1, 0.1)], 60, 1.0, 1.0
        )
        entry = next(c for c in fused if c["chunk_id"] == "only_sem")
        self.assertEqual(entry["matched_by"], ["semantic"])
        self.assertIsNone(entry["bm25_rank"])
        self.assertIsNone(entry["bm25_score"])

    def test_matched_by_both_branches(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 5.0)], [_sem_cand("c1", 1, 0.1)], 60, 1.0, 1.0
        )
        self.assertEqual(fused[0]["matched_by"], ["bm25", "semantic"])

    def test_metadata_mismatch_fails(self):
        for field, bm25_kwargs, sem_kwargs in (
            ("text", {"text": "noi dung A"}, {"text": "noi dung B"}),
            ("source", {"source": "a.pdf"}, {"source": "b.pdf"}),
            ("page_start", {"p1": 1}, {"p1": 9}),
            ("page_end", {"p2": 2}, {"p2": 8}),
        ):
            with self.subTest(field=field):
                with self.assertRaises(rag.DataError) as ctx:
                    ar.reciprocal_rank_fusion(
                        [_bm25_cand("c1", 1, 5.0, **bm25_kwargs)],
                        [_sem_cand("c1", 1, 0.1, **sem_kwargs)],
                        60, 1.0, 1.0,
                    )
                self.assertIn("c1", str(ctx.exception))

    def test_empty_both_branches(self):
        self.assertEqual(ar.reciprocal_rank_fusion([], [], 60, 1.0, 1.0), [])

    def test_schema_complete(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 5.0)], [_sem_cand("c1", 2, 0.1)], 60, 1.0, 1.0
        )
        required = {
            "chunk_id", "text", "source", "page_start", "page_end",
            "bm25_rank", "bm25_score", "semantic_rank", "semantic_distance",
            "rrf_score", "fused_rank", "matched_by",
        }
        self.assertTrue(required.issubset(fused[0].keys()), f"Thiếu: {required - set(fused[0].keys())}")


class RRFOrderingTests(unittest.TestCase):
    def test_sorted_by_rrf_score_descending(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("c1", 1, 5.0), _bm25_cand("c2", 2, 4.0), _bm25_cand("c3", 3, 3.0)],
            [_sem_cand("c3", 1, 0.1)],
            60, 1.0, 1.0,
        )
        scores = [c["rrf_score"] for c in fused]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_fused_rank_sequential_from_one(self):
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand(f"c{i}", i, 10.0 - i) for i in range(1, 6)], [], 60, 1.0, 1.0
        )
        self.assertEqual([c["fused_rank"] for c in fused], [1, 2, 3, 4, 5])

    def test_appearing_in_both_branches_ranks_higher(self):
        """Chunk được cả 2 nhánh tìm thấy phải được RRF đẩy lên trên."""
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("both", 2, 4.0), _bm25_cand("bm25_top", 1, 9.0)],
            [_sem_cand("both", 2, 0.2), _sem_cand("sem_top", 1, 0.1)],
            60, 1.0, 1.0,
        )
        ranks = {c["chunk_id"]: c["fused_rank"] for c in fused}
        self.assertLess(ranks["both"], ranks["bm25_top"])
        self.assertLess(ranks["both"], ranks["sem_top"])

    def test_tie_break_deterministic(self):
        """Cùng rrf_score -> thứ tự phải ổn định và theo đúng quy tắc tie-break."""
        bm25 = [_bm25_cand("z", 1, 5.0), _bm25_cand("a", 1, 5.0), _bm25_cand("m", 1, 5.0)]
        # cùng rank 1 ở bm25 (giả lập), không có semantic -> cùng rrf_score
        first = [c["chunk_id"] for c in ar.reciprocal_rank_fusion(bm25, [], 60, 1.0, 1.0)]
        second = [c["chunk_id"] for c in ar.reciprocal_rank_fusion(bm25, [], 60, 1.0, 1.0)]
        self.assertEqual(first, second, "Phải deterministic")
        self.assertEqual(first, ["a", "m", "z"], "Tie-break cuối cùng theo chunk_id")

    def test_tie_break_prefers_best_rank_then_semantic(self):
        """Cùng rrf_score: ưu tiên rank tốt nhất giữa 2 nhánh, rồi tới semantic rank."""
        fused = ar.reciprocal_rank_fusion(
            [_bm25_cand("bm25_r1", 1, 5.0)],
            [_sem_cand("sem_r1", 1, 0.1)],
            60, 1.0, 1.0,
        )
        # cả hai đều rrf = 1/61; sem_r1 có semantic_rank=1, bm25_r1 có semantic_rank=None(inf)
        self.assertEqual(fused[0]["chunk_id"], "sem_r1")


# ---------------------------------------------------------------------------
# hybrid_search — gọi mỗi retriever đúng 1 lần, có trace, không rerank/generation
# ---------------------------------------------------------------------------


def _vector(text, dim, salt=""):
    h = hashlib.sha256((salt + text).encode("utf-8")).digest()
    return [((h[i % len(h)] / 255.0) - 0.5) + (i + 1) * 1e-6 for i in range(dim)]


class _FakeModels:
    def __init__(self, dim, salt):
        self.dim, self.salt = dim, salt
        self.embed_calls = 0

    def embed_content(self, model, contents, config):
        self.embed_calls += 1
        return type("R", (), {"embeddings": [type("E", (), {"values": _vector(contents, self.dim, self.salt)})]})

    def generate_content(self, model, contents):
        raise AssertionError("Bước 06 không được gọi generation")


class _FakeClient:
    def __init__(self, dim, salt):
        self.models = _FakeModels(dim, salt)


def _write_env(path: Path, **overrides) -> Path:
    values = {
        "GEMINI_API_KEY": "fake-key",
        "GEMINI_EMBEDDING_MODEL": "gemini-embedding-2",
        "GEMINI_EMBEDDING_DIM": str(DIM),
        "GEMINI_GENERATION_MODEL": "gemini-3.5-flash-lite",
        "RAG_MAX_DISTANCE": "0.45",
        "BM25_CANDIDATES": "5",
        "SEMANTIC_CANDIDATES": "5",
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


class HybridSearchTests(unittest.TestCase):
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

    def _hybrid(self, question="Điều 7 cơ cấu lại thời hạn trả nợ"):
        return ar.hybrid_search(
            question, self.config, "hierarchical",
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            client_factory=lambda k: _FakeClient(DIM, "query"),
        )

    def test_trace_counts_correct(self):
        result = self._hybrid()
        trace = result["trace"]
        bm25_ids = {c["chunk_id"] for c in result["bm25_candidates"]}
        sem_ids = {c["chunk_id"] for c in result["semantic_candidates"]}
        self.assertEqual(trace["bm25_candidate_count"], len(result["bm25_candidates"]))
        self.assertEqual(trace["semantic_candidate_count"], len(result["semantic_candidates"]))
        self.assertEqual(trace["union_count"], len(bm25_ids | sem_ids))
        self.assertEqual(trace["overlap_count"], len(bm25_ids & sem_ids))
        self.assertEqual(trace["fused_count"], len(result["candidates"]))
        self.assertEqual(trace["fused_count"], trace["union_count"])

    def test_trace_has_all_latency_keys(self):
        lat = self._hybrid()["trace"]["latency_ms"]
        for key in ("bm25", "semantic", "fusion", "total"):
            self.assertIn(key, lat)
            self.assertIsInstance(lat[key], float)
            self.assertGreaterEqual(lat[key], 0.0)

    def test_trace_records_config(self):
        trace = self._hybrid()["trace"]
        self.assertEqual(trace["rrf_k"], 60)
        self.assertEqual(trace["rrf_bm25_weight"], 1.0)
        self.assertEqual(trace["rrf_semantic_weight"], 1.0)

    def test_each_retriever_called_exactly_once(self):
        calls = {"bm25": 0, "semantic": 0}
        orig_bm25, orig_sem = ar.bm25_search, ar.semantic_search

        def spy_bm25(*a, **kw):
            calls["bm25"] += 1
            return orig_bm25(*a, **kw)

        def spy_sem(*a, **kw):
            calls["semantic"] += 1
            return orig_sem(*a, **kw)

        try:
            ar.bm25_search, ar.semantic_search = spy_bm25, spy_sem
            self._hybrid()
        finally:
            ar.bm25_search, ar.semantic_search = orig_bm25, orig_sem

        self.assertEqual(calls, {"bm25": 1, "semantic": 1})

    def test_reuses_prebuilt_bm25_index(self):
        chunks, _ = rag.load_chunks(input_dir=FIXTURE_DIR, strategy="hierarchical")
        index = ar.build_bm25_index(chunks)
        result = ar.hybrid_search(
            "Điều 7", self.config, "hierarchical", bm25_index=index,
            chunks_dir=FIXTURE_DIR, persist_path=self.chroma,
            client_factory=lambda k: _FakeClient(DIM, "query"),
        )
        self.assertTrue(result["candidates"])

    def test_no_rerank_fields_yet(self):
        """Bước 06 chưa rerank — không được có field rerank giả."""
        for c in self._hybrid()["candidates"]:
            self.assertNotIn("rerank_score", c)
            self.assertNotIn("rerank_rank", c)

    def test_no_generation_called(self):
        """_FakeModels.generate_content sẽ raise nếu bị gọi."""
        self.assertTrue(self._hybrid()["candidates"])

    def test_no_model_loaded(self):
        """Hybrid không được import/tải reranker."""
        source = (Path(__file__).resolve().parent.parent / "advanced_rag.py").read_text(encoding="utf-8")
        in_hybrid = source.split("def hybrid_search")[1].split("\ndef ")[0]
        self.assertNotIn("transformers", in_hybrid)
        self.assertNotIn("torch", in_hybrid)


if __name__ == "__main__":
    unittest.main()
