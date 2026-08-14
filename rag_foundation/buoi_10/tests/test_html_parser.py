import unittest
from pathlib import Path

from src.html_parser import (
    Chunk,
    build_hierarchy,
    classify_level,
    clean_html,
    extract_blocks,
    parse_html_document,
    RawBlock,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_law.html"


class ClassifyLevelTests(unittest.TestCase):
    def test_chuong_heading(self):
        level, heading = classify_level(RawBlock(text="Chương I QUY ĐỊNH CHUNG"))
        self.assertEqual(level, "chuong")
        self.assertEqual(heading, "Chương I QUY ĐỊNH CHUNG")

    def test_dieu_heading_requires_dot(self):
        level, _ = classify_level(RawBlock(text="Điều 7. Nguyên tắc"))
        self.assertEqual(level, "dieu")

    def test_dieu_reference_mid_text_is_not_heading(self):
        # Bẫy đã ghi nhận ở Buổi 09: "Điều N" giữa câu không phải heading.
        level, heading = classify_level(
            RawBlock(text="Thông tư có hiệu lực, tham chiếu quy định tại Điều 1 nêu trên.")
        )
        self.assertEqual(level, "doan")
        self.assertIsNone(heading)

    def test_table_is_bang(self):
        level, _ = classify_level(RawBlock(text="CAR | 8%", is_table=True))
        self.assertEqual(level, "bang")


class ExtractBlocksTests(unittest.TestCase):
    def test_extracts_headings_paragraphs_and_table(self):
        html = FIXTURE.read_text(encoding="utf-8")
        soup = clean_html(html)
        blocks = extract_blocks(soup)
        texts = [b.text for b in blocks]
        self.assertIn("Chương I QUY ĐỊNH CHUNG", texts)
        self.assertIn("Điều 1. Phạm vi điều chỉnh", texts)
        self.assertTrue(any(b.is_table for b in blocks))


class BuildHierarchyTests(unittest.TestCase):
    def setUp(self):
        html = FIXTURE.read_text(encoding="utf-8")
        self.chunks = parse_html_document("doc-test", html)

    def test_produces_chunks(self):
        self.assertGreater(len(self.chunks), 0)

    def test_two_chapters_at_root(self):
        chuongs = [c for c in self.chunks if c.level == "chuong"]
        self.assertEqual(len(chuongs), 2)
        for c in chuongs:
            self.assertIsNone(c.parent_id)

    def test_dieu_children_of_chuong(self):
        chuong1 = next(c for c in self.chunks if c.level == "chuong" and "I" in (c.heading or ""))
        dieu_children = [
            c for c in self.chunks if c.level == "dieu" and c.parent_id == chuong1.chunk_id
        ]
        self.assertEqual(len(dieu_children), 2)  # Điều 1, Điều 2

    def test_paragraph_child_of_dieu(self):
        dieu1 = next(c for c in self.chunks if c.level == "dieu" and c.heading and c.heading.startswith("Điều 1."))
        paragraphs = [c for c in self.chunks if c.parent_id == dieu1.chunk_id]
        self.assertGreaterEqual(len(paragraphs), 1)
        for p in paragraphs:
            self.assertEqual(p.level, "doan")

    def test_table_becomes_bang_chunk(self):
        bang_chunks = [c for c in self.chunks if c.level == "bang"]
        self.assertEqual(len(bang_chunks), 1)
        self.assertIn("CAR", bang_chunks[0].text)

    def test_chunk_ids_stable_across_runs(self):
        html = FIXTURE.read_text(encoding="utf-8")
        chunks_again = parse_html_document("doc-test", html)
        ids_first = [c.chunk_id for c in self.chunks]
        ids_second = [c.chunk_id for c in chunks_again]
        self.assertEqual(ids_first, ids_second)

    def test_order_index_is_monotonic(self):
        indices = [c.order_index for c in self.chunks]
        self.assertEqual(indices, sorted(indices))

    def test_chunk_to_dict_roundtrip_keys(self):
        d = self.chunks[0].to_dict()
        self.assertEqual(
            set(d.keys()),
            {"doc_id", "chunk_id", "level", "heading", "text", "order_index", "parent_id", "warnings"},
        )


class DocumentFallbackTests(unittest.TestCase):
    def test_paragraph_before_any_heading_gets_fallback_warning(self):
        blocks = [RawBlock(text="Đoạn mở đầu không có heading nào phía trước.")]
        chunks = build_hierarchy("doc-x", blocks)
        self.assertEqual(len(chunks), 1)
        self.assertIsNone(chunks[0].parent_id)
        self.assertTrue(any("document_fallback" in w for w in chunks[0].warnings))


if __name__ == "__main__":
    unittest.main()
