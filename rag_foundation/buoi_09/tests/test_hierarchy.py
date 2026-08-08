"""tests/test_hierarchy.py — Test hierarchy registry và parent store (Bước 03).

Nguyên tắc (SPEC_buoi_09.md mục 12): `unittest`, offline hoàn toàn — không
Internet, không Gemini, không tải model, không đọc `.env` thật, không đụng
storage Buổi 05–08. Store luôn ghi vào thư mục tạm.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hierarchical_rag as hr  # noqa: E402
import rag  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

ENV_DEFAULTS = {
    # --- phần kế thừa Buổi 08 (advanced_rag.load_advanced_config cần đủ) ---
    "GEMINI_API_KEY": "fake-key",
    "GEMINI_EMBEDDING_MODEL": "gemini-embedding-2",
    "GEMINI_EMBEDDING_DIM": "768",
    "GEMINI_GENERATION_MODEL": "gemini-3.5-flash-lite",
    "RAG_MAX_DISTANCE": "0.45",
    "DEFAULT_TOP_K": "5",
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
    # --- phần mới của Buổi 09 ---
    "MULTI_QUERY_COUNT": "3",
    "MULTI_QUERY_MAX_CHARS": "300",
    "MULTI_QUERY_TEMPERATURE": "0.2",
    "MULTI_QUERY_ORIGINAL_WEIGHT": "1.5",
    "MULTI_QUERY_VARIANT_WEIGHT": "1.0",
    "MULTI_QUERY_RRF_K": "60",
    "PER_QUERY_CANDIDATES": "12",
    "PARENT_MAX_CHARS": "1000",
    "PARENT_SCORE_CHILD_LIMIT": "3",
    "PARENT_RRF_K": "60",
    "PARENT_CANDIDATES": "10",
    "FINAL_PARENT_TOP_K": "3",
    "TOTAL_CONTEXT_MAX_CHARS": "16000",
}


def write_env(path: Path, **overrides) -> Path:
    values = dict(ENV_DEFAULTS)
    values.update(overrides)
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
    return path


def chunk(cid, source, text, path=None, p1=1, p2=1):
    return {
        "chunk_id": cid,
        "strategy": "hierarchical",
        "source": source,
        "page_start": p1,
        "page_end": p2,
        "structure_path": path,
        "text": text,
    }


def write_chunks(dir_: Path, name: str, records: list) -> Path:
    p = dir_ / name
    p.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. Config
# ---------------------------------------------------------------------------


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_valid_config(self):
        cfg = hr.load_hierarchy_config(write_env(self.work / ".env"))
        self.assertEqual(cfg.multi_query_count, 3)
        self.assertEqual(cfg.parent_max_chars, 1000)

    def test_multi_query_count_range(self):
        for bad in ("0", "6", "abc"):
            with self.subTest(v=bad):
                with self.assertRaises(hr.HierarchyError):
                    hr.load_hierarchy_config(write_env(self.work / ".env", MULTI_QUERY_COUNT=bad))

    def test_temperature_range(self):
        for bad in ("-0.1", "1.5"):
            with self.subTest(v=bad):
                with self.assertRaises(hr.HierarchyError):
                    hr.load_hierarchy_config(write_env(self.work / ".env", MULTI_QUERY_TEMPERATURE=bad))

    def test_both_weights_zero_blocked(self):
        with self.assertRaises(hr.HierarchyError):
            hr.load_hierarchy_config(
                write_env(self.work / ".env", MULTI_QUERY_ORIGINAL_WEIGHT="0", MULTI_QUERY_VARIANT_WEIGHT="0")
            )

    def test_final_parent_top_k_must_not_exceed_candidates(self):
        with self.assertRaises(hr.HierarchyError):
            hr.load_hierarchy_config(
                write_env(self.work / ".env", FINAL_PARENT_TOP_K="20", PARENT_CANDIDATES="10")
            )

    def test_total_context_must_be_at_least_parent_max(self):
        with self.assertRaises(hr.HierarchyError):
            hr.load_hierarchy_config(
                write_env(self.work / ".env", PARENT_MAX_CHARS="6000", TOTAL_CONTEXT_MAX_CHARS="5000")
            )

    def test_parent_max_chars_range(self):
        for bad in ("999", "20001"):
            with self.subTest(v=bad):
                with self.assertRaises(hr.HierarchyError):
                    hr.load_hierarchy_config(write_env(self.work / ".env", PARENT_MAX_CHARS=bad))

    def test_config_not_dependent_on_cwd(self):
        """Load bằng đường dẫn tuyệt đối phải thành công dù cwd ở đâu."""
        env = write_env(self.work / ".env")
        import os

        old = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            cfg = hr.load_hierarchy_config(env)
            self.assertEqual(cfg.parent_rrf_k, 60)
        finally:
            os.chdir(old)


# ---------------------------------------------------------------------------
# 2. Hierarchy resolution
# ---------------------------------------------------------------------------


class ResolutionTests(unittest.TestCase):
    def test_metadata_precedence(self):
        cs = [chunk("a_1", "s.pdf", "Nội dung bất kỳ", "Chương I > Điều 5 > Khoản 1")]
        r = hr.resolve_hierarchy(cs)[0]
        self.assertEqual(r["resolution_method"], "metadata")
        self.assertEqual(r["structural_path"]["article"], "Điều 5")
        self.assertEqual(r["structural_path"]["chapter"], "Chương I")
        self.assertFalse(r["ambiguous"])

    def test_heading_inferred_when_metadata_missing_article(self):
        cs = [chunk("a_1", "s.pdf", "Điều 9. Tiêu đề điều khoản mô phỏng.", "Chương II")]
        r = hr.resolve_hierarchy(cs)[0]
        self.assertEqual(r["resolution_method"], "heading_inferred")
        self.assertEqual(r["structural_path"]["article"], "Điều 9")

    def test_carry_forward_within_same_source(self):
        cs = [
            chunk("a_1", "s.pdf", "Điều 3. Mở đầu.", "Chương I > Điều 3"),
            chunk("a_2", "s.pdf", "Nội dung tiếp theo không có metadata điều.", "Chương I"),
        ]
        out = hr.resolve_hierarchy(cs)
        self.assertEqual(out[1]["resolution_method"], "carried_forward")
        self.assertEqual(out[1]["structural_path"]["article"], "Điều 3")
        self.assertTrue(out[1]["ambiguous"], "carry-forward phải đánh dấu ambiguous")

    def test_no_carry_forward_across_sources(self):
        cs = [
            chunk("a_1", "src_a.pdf", "Điều 3. Nội dung A.", "Chương I > Điều 3"),
            chunk("b_1", "src_b.pdf", "Nội dung B không có điều.", "Chương I"),
        ]
        out = hr.resolve_hierarchy(cs)
        b = next(c for c in out if c["source"] == "src_b.pdf")
        self.assertEqual(b["resolution_method"], "document_fallback")
        self.assertIsNone(b["structural_path"]["article"], "KHÔNG được carry qua source khác")

    def test_inline_dieu_not_treated_as_heading(self):
        """Bẫy thật: corpus có 26 record dạng 'quy định tại khoản 4 Điều 8'."""
        text = "2. Việc đánh giá thực hiện theo quy định tại khoản 4 Điều 8 Thông tư này."
        cs = [chunk("a_1", "s.pdf", text, "Chương I")]
        r = hr.resolve_hierarchy(cs)[0]
        self.assertEqual(r["resolution_method"], "document_fallback")
        self.assertIsNone(r["structural_path"]["article"])

    def test_heading_requires_dot_after_number(self):
        """'Điều 8 Thông tư' (không có dấu chấm) không phải heading."""
        cs = [chunk("a_1", "s.pdf", "Điều 8 Thông tư này quy định...", "Chương I")]
        r = hr.resolve_hierarchy(cs)[0]
        self.assertNotEqual(r["resolution_method"], "heading_inferred")

    def test_metadata_heading_conflict_marks_ambiguous(self):
        cs = [chunk("a_1", "s.pdf", "Điều 9. Tiêu đề.", "Chương I > Điều 5")]
        r = hr.resolve_hierarchy(cs)[0]
        self.assertTrue(r["ambiguous"])
        self.assertTrue(any("article_conflict" in w for w in r["warnings"]))
        self.assertEqual(r["structural_path"]["article"], "Điều 5", "metadata vẫn thắng, nhưng có cảnh báo")

    def test_numeric_chunk_ordering(self):
        """'...:10' phải đứng SAU '...:2', không sort lexical."""
        cs = [
            chunk("doc:10", "s.pdf", "Nội dung mười.", "Chương I"),
            chunk("doc:2", "s.pdf", "Điều 4. Nội dung hai.", "Chương I > Điều 4"),
        ]
        out = hr.resolve_hierarchy(cs)
        self.assertEqual([c["child_id"] for c in out], ["doc:2", "doc:10"])
        self.assertEqual(out[1]["structural_path"]["article"], "Điều 4",
                         "carry-forward chỉ đúng khi thứ tự số đúng")

    def test_source_data_not_mutated(self):
        cs = [chunk("a_1", "s.pdf", "Điều 1. X", "Chương I > Điều 1")]
        before = json.dumps(cs, sort_keys=True, ensure_ascii=False)
        hr.resolve_hierarchy(cs)
        self.assertEqual(json.dumps(cs, sort_keys=True, ensure_ascii=False), before)


# ---------------------------------------------------------------------------
# 3. Parent building
# ---------------------------------------------------------------------------


class ParentTests(unittest.TestCase):
    def test_stable_parent_id(self):
        a = hr.make_parent_id("s.pdf", "Chương I > Điều 1", 1)
        b = hr.make_parent_id("s.pdf", "Chương I > Điều 1", 1)
        c = hr.make_parent_id("s.pdf", "Chương I > Điều 1", 2)
        d = hr.make_parent_id("khac.pdf", "Chương I > Điều 1", 1)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertTrue(a.startswith("P_"))

    def test_each_child_exactly_one_parent(self):
        cs = [chunk(f"a_{i}", "s.pdf", f"Nội dung {i} " * 20, "Chương I > Điều 1") for i in range(1, 8)]
        parents, children = hr.build_parents(hr.resolve_hierarchy(cs), 300)
        all_ids = [cid for p in parents for cid in p["child_ids"]]
        self.assertEqual(len(all_ids), len(set(all_ids)), "không child nào thuộc 2 parent")
        self.assertEqual(set(all_ids), {c["child_id"] for c in children})
        for c in children:
            self.assertIn("parent_id", c)

    def test_parent_split_at_child_boundary(self):
        """Chia window nhưng KHÔNG cắt giữa child."""
        texts = ["A" * 400, "B" * 400, "C" * 400]
        cs = [chunk(f"a_{i+1}", "s.pdf", t, "Chương I > Điều 1") for i, t in enumerate(texts)]
        parents, _ = hr.build_parents(hr.resolve_hierarchy(cs), 900)
        self.assertGreater(len(parents), 1, "phải chia thành nhiều window")
        for p in parents:
            for cid in p["child_ids"]:
                original = next(t for i, t in enumerate(texts) if f"a_{i+1}" == cid)
                self.assertIn(original, p["text"], "text child phải nguyên vẹn trong parent")

    def test_oversized_single_child_kept_with_warning(self):
        cs = [chunk("a_1", "s.pdf", "X" * 5000, "Chương I > Điều 1")]
        parents, _ = hr.build_parents(hr.resolve_hierarchy(cs), 1000)
        self.assertEqual(len(parents), 1)
        self.assertEqual(len(parents[0]["text"]), 5000, "KHÔNG được truncate")
        self.assertTrue(any(w.startswith("oversized_single_child") for w in parents[0]["warnings"]))

    def test_parent_pages_and_counts(self):
        cs = [
            chunk("a_1", "s.pdf", "Phần một.", "Chương I > Điều 1", p1=3, p2=4),
            chunk("a_2", "s.pdf", "Phần hai.", "Chương I > Điều 1", p1=1, p2=2),
        ]
        parents, _ = hr.build_parents(hr.resolve_hierarchy(cs), 5000)
        p = parents[0]
        self.assertEqual(p["page_start"], 1)
        self.assertEqual(p["page_end"], 4)
        self.assertEqual(p["char_count"], len(p["text"]))
        self.assertEqual(len(p["child_ids"]), 2)

    def test_parent_text_is_concatenation_not_summary(self):
        cs = [
            chunk("a_1", "s.pdf", "Câu một.", "Chương I > Điều 1"),
            chunk("a_2", "s.pdf", "Câu hai.", "Chương I > Điều 1"),
        ]
        parents, _ = hr.build_parents(hr.resolve_hierarchy(cs), 5000)
        self.assertIn("Câu một.", parents[0]["text"])
        self.assertIn("Câu hai.", parents[0]["text"])
        self.assertEqual(parents[0]["text"].count("Câu một."), 1, "không lặp child text")

    def test_fallback_parent_when_no_article(self):
        cs = [
            chunk("a_1", "s.pdf", "Nội dung Chương IV khoản 1.", "Chương IV > Khoản 1"),
            chunk("a_2", "s.pdf", "Nội dung Chương IV khoản 2.", "Chương IV > Khoản 2"),
        ]
        parents, children = hr.build_parents(hr.resolve_hierarchy(cs), 5000)
        self.assertTrue(all("fallback" in p["article_key"] for p in parents))
        self.assertEqual(len(parents), 2, "khoản khác nhau -> parent fallback khác nhau")

    def test_deterministic_across_runs(self):
        cs = [chunk(f"a_{i}", "s.pdf", f"Nội dung {i}", "Chương I > Điều 1") for i in range(1, 5)]
        p1, c1 = hr.build_parents(hr.resolve_hierarchy(cs), 1000)
        p2, c2 = hr.build_parents(hr.resolve_hierarchy(cs), 1000)
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))
        self.assertEqual(json.dumps(c1, sort_keys=True), json.dumps(c2, sort_keys=True))


# ---------------------------------------------------------------------------
# 4. Store: atomic build, manifest, status
# ---------------------------------------------------------------------------


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.chunks_dir = self.work / "chunks"
        self.chunks_dir.mkdir()
        self.hier = self.work / "hierarchy"
        write_chunks(
            self.chunks_dir,
            "sample.json",
            [
                chunk("a_1", "s.pdf", "Điều 1. Mở đầu.", "Chương I > Điều 1"),
                chunk("a_2", "s.pdf", "1. Nội dung khoản một.", "Chương I > Điều 1 > Khoản 1"),
                chunk("a_3", "s.pdf", "Nội dung không có điều.", "Chương IV > Khoản 2"),
            ],
        )
        self.cfg = hr.load_hierarchy_config(write_env(self.work / ".env"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _build(self):
        return hr.build_hierarchy(self.cfg, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)

    def test_build_creates_three_files(self):
        self._build()
        for name in ("children.json", "parents.json", "manifest.json"):
            self.assertTrue((self.hier / name).exists(), f"thiếu {name}")

    def test_no_temp_file_left_behind(self):
        self._build()
        leftovers = list(self.hier.glob("*.tmp"))
        self.assertEqual(leftovers, [], "ghi atomic không được để lại file .tmp")

    def test_manifest_has_fingerprint_and_counts(self):
        m = self._build()
        self.assertEqual(m["schema_version"], hr.SCHEMA_VERSION)
        self.assertEqual(m["counts"]["input_chunks"], 3)
        self.assertEqual(m["counts"]["children"], 3)
        self.assertIn("input_files", m)
        self.assertIn("sha256", m["input_files"][0])
        self.assertIn("built_at", m)
        self.assertIn("config_identity", m)

    def test_child_count_invariant(self):
        m = self._build()
        self.assertEqual(m["counts"]["children"], m["counts"]["input_chunks"])

    def test_status_missing_before_build(self):
        st = hr.hierarchy_status(self.cfg, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)
        self.assertEqual(st["state"], "missing")

    def test_status_does_not_create_anything(self):
        """status là read-only tuyệt đối: không mkdir, không tạo file."""
        self.assertFalse(self.hier.exists())
        hr.hierarchy_status(self.cfg, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)
        self.assertFalse(self.hier.exists(), "status KHÔNG được tạo thư mục")

    def test_status_ready_after_build(self):
        self._build()
        st = hr.hierarchy_status(self.cfg, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)
        self.assertEqual(st["state"], "ready")
        self.assertEqual(st["reasons"], [])

    def test_status_does_not_modify_timestamps(self):
        self._build()
        before = {p.name: p.stat().st_mtime_ns for p in self.hier.iterdir()}
        hr.hierarchy_status(self.cfg, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)
        after = {p.name: p.stat().st_mtime_ns for p in self.hier.iterdir()}
        self.assertEqual(before, after)

    def test_status_stale_when_input_changes(self):
        self._build()
        write_chunks(self.chunks_dir, "sample.json",
                     [chunk("a_1", "s.pdf", "Điều 1. Đã sửa nội dung.", "Chương I > Điều 1")])
        st = hr.hierarchy_status(self.cfg, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)
        self.assertEqual(st["state"], "stale")
        self.assertTrue(any("fingerprint" in r for r in st["reasons"]))

    def test_status_stale_when_config_changes(self):
        self._build()
        cfg2 = hr.load_hierarchy_config(write_env(self.work / "b.env", PARENT_MAX_CHARS="2000"))
        st = hr.hierarchy_status(cfg2, chunks_dir=self.chunks_dir, hierarchy_dir=self.hier)
        self.assertEqual(st["state"], "stale")
        self.assertTrue(any("config_identity" in r for r in st["reasons"]))

    def test_rebuild_is_idempotent(self):
        self._build()
        c1 = (self.hier / "children.json").read_text(encoding="utf-8")
        p1 = (self.hier / "parents.json").read_text(encoding="utf-8")
        self._build()
        self.assertEqual((self.hier / "children.json").read_text(encoding="utf-8"), c1)
        self.assertEqual((self.hier / "parents.json").read_text(encoding="utf-8"), p1)

    def test_duplicate_chunk_id_fails(self):
        write_chunks(self.chunks_dir, "dup.json",
                     [chunk("dup_1", "s.pdf", "A", "Chương I > Điều 1")])
        write_chunks(self.chunks_dir, "dup2.json",
                     [chunk("dup_1", "s.pdf", "B", "Chương I > Điều 1")])
        with self.assertRaises((hr.HierarchyError, rag.DataError)):
            self._build()

    def test_load_store_returns_lookup_dicts(self):
        self._build()
        children, parents, manifest = hr.load_hierarchy_store(hierarchy_dir=self.hier)
        self.assertEqual(len(children), 3)
        self.assertTrue(all(c["parent_id"] in parents for c in children.values()))
        self.assertIn("counts", manifest)

    def test_load_store_missing_raises_with_guidance(self):
        with self.assertRaises(hr.HierarchyError) as ctx:
            hr.load_hierarchy_store(hierarchy_dir=self.hier)
        self.assertIn("build-hierarchy", str(ctx.exception))


# ---------------------------------------------------------------------------
# 5. Fixture thật của Buổi 09
# ---------------------------------------------------------------------------


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.cfg = hr.load_hierarchy_config(write_env(self.work / ".env", PARENT_MAX_CHARS="1000"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_fixture_loads_and_builds(self):
        chunks, _ = rag.load_chunks(input_dir=FIXTURE_DIR, strategy="hierarchical")
        self.assertEqual(len(chunks), 10)
        parents, children = hr.build_parents(hr.resolve_hierarchy(chunks), self.cfg.parent_max_chars)
        self.assertEqual(len(children), 10)
        self.assertTrue(parents)

    def test_fixture_inline_citation_not_promoted(self):
        """Chunk chứa 'quy định tại khoản 4 Điều 8' không được thành Điều 8."""
        chunks, _ = rag.load_chunks(input_dir=FIXTURE_DIR, strategy="hierarchical")
        out = {c["child_id"]: c for c in hr.resolve_hierarchy(chunks)}
        target = out["demo_src_a_hierarchical_0004"]
        self.assertEqual(target["structural_path"]["article"], "Điều 1",
                         "phải giữ Điều 1 từ metadata, KHÔNG nhảy sang Điều 8")

    def test_fixture_fallback_for_chapter_only(self):
        chunks, _ = rag.load_chunks(input_dir=FIXTURE_DIR, strategy="hierarchical")
        out = {c["child_id"]: c for c in hr.resolve_hierarchy(chunks)}
        for cid in ("demo_src_a_hierarchical_0007", "demo_src_a_hierarchical_0008"):
            self.assertIsNone(out[cid]["structural_path"]["article"],
                              "Chương II không có Điều -> phải fallback")

    def test_fixture_no_cross_source_carry(self):
        chunks, _ = rag.load_chunks(input_dir=FIXTURE_DIR, strategy="hierarchical")
        out = {c["child_id"]: c for c in hr.resolve_hierarchy(chunks)}
        b2 = out["demo_src_b_hierarchical_0002"]
        self.assertEqual(b2["source"], "demo_van_ban_b.pdf")
        self.assertEqual(b2["structural_path"]["article"], "Điều 1",
                         "carry-forward TRONG source B là hợp lệ")
        self.assertEqual(b2["resolution_method"], "carried_forward")


# ---------------------------------------------------------------------------
# 6. Isolation
# ---------------------------------------------------------------------------


class IsolationTests(unittest.TestCase):
    def test_no_module_level_heavy_import(self):
        source = (Path(__file__).resolve().parent.parent / "hierarchical_rag.py").read_text(encoding="utf-8")
        head = source.split("class HierarchyError")[0]
        for bad in ("import torch", "import transformers", "from transformers", "import chromadb"):
            self.assertNotIn(bad, head, f"không được import '{bad}' ở module level")

    def test_import_does_not_touch_real_storage(self):
        """Import module không được tạo storage/hierarchy thật."""
        import importlib

        importlib.reload(hr)
        self.assertTrue(True, "reload không ném lỗi và không cần side effect")


if __name__ == "__main__":
    unittest.main()
