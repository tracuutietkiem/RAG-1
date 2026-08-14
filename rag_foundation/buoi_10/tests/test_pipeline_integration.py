"""Test tích hợp offline: HTML sinh từ md_to_html chạy hết được qua parser + loader.

Không cần Neo4j thật, không cần model embedding thật, không đọc dữ liệu Buổi 05.
"""

import unittest

from src.embedding import warn_long_texts
from src.html_parser import extract_doc_meta, parse_html_document
from src.md_to_html import build_html_document, extract_doc_info, markdown_to_html_body
from src.neo4j_loader import (
    DocRelationship,
    DocumentMeta,
    compute_next_links,
    load_document_chunks,
    load_document_relationships,
)
from tests.test_neo4j_loader import FakeSession

MARKDOWN = """# NGÂN HÀNG NHÀ NƯỚC VIỆT NAM

Số: 41 /2016/TT-NHNN

# Quy định tỷ lệ an toàn vốn

Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12 ngày 16 tháng 6 năm 2010;

# Chương I
## Điều 1. Phạm vi điều chỉnh

1. Thông tư này quy định tỷ lệ an toàn vốn.

2. Đối tượng áp dụng gồm:

a) Ngân hàng thương mại;

b) Chi nhánh ngân hàng nước ngoài.

## Điều 2. Giải thích từ ngữ

1. Tài sản tài chính gồm:

a) Tiền mặt;

<table>
  <tr><th>Cấu phần</th><th>Tỷ lệ</th></tr>
  <tr><td>CAR</td><td>8%</td></tr>
</table>
"""


def _make_html() -> tuple[str, str]:
    info = extract_doc_info(MARKDOWN, fallback_title="test")
    body = markdown_to_html_body(MARKDOWN)
    return info.doc_id, build_html_document(info, body, "ghi chú test")


class EndToEndParseTests(unittest.TestCase):
    def setUp(self):
        self.doc_id, self.html = _make_html()
        self.chunks = parse_html_document(self.doc_id, self.html)
        self.by_id = {c.chunk_id: c for c in self.chunks}

    def test_doc_id_readable_from_meta(self):
        meta = extract_doc_meta(self.html)
        self.assertEqual(meta["doc-id"], "41/2016/TT-NHNN")

    def test_hierarchy_levels_detected(self):
        levels = {c.level for c in self.chunks}
        self.assertIn("chuong", levels)
        self.assertIn("dieu", levels)
        self.assertIn("khoan", levels)
        self.assertIn("diem", levels)
        self.assertIn("bang", levels)

    def test_diem_nested_under_khoan_under_dieu(self):
        diem = next(c for c in self.chunks if c.level == "diem")
        khoan = self.by_id[diem.parent_id]
        self.assertEqual(khoan.level, "khoan")
        dieu = self.by_id[khoan.parent_id]
        self.assertEqual(dieu.level, "dieu")
        chuong = self.by_id[dieu.parent_id]
        self.assertEqual(chuong.level, "chuong")

    def test_khoan_not_detected_outside_dieu(self):
        # Dòng "Số: 41 /2016/TT-NHNN" và phần Căn cứ nằm trước Điều đầu tiên,
        # không được nhận nhầm thành Khoản.
        preamble = [c for c in self.chunks if c.parent_id is None]
        self.assertTrue(preamble)
        self.assertTrue(all(c.level in ("doan", "chuong") for c in preamble))

    def test_no_orphan_parent_reference(self):
        for c in self.chunks:
            if c.parent_id is not None:
                self.assertIn(c.parent_id, self.by_id)

    def test_chunk_ids_unique(self):
        ids = [c.chunk_id for c in self.chunks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_next_links_never_cross_parents(self):
        pairs = compute_next_links(self.chunks)
        for a_id, b_id in pairs:
            self.assertEqual(self.by_id[a_id].parent_id, self.by_id[b_id].parent_id)

    def test_short_texts_not_flagged_as_too_long(self):
        self.assertEqual(warn_long_texts([c.text for c in self.chunks]), [])


class EndToEndLoadTests(unittest.TestCase):
    def test_full_load_sequence_against_fake_session(self):
        doc_id, html = _make_html()
        chunks = parse_html_document(doc_id, html)
        embeddings = {c.chunk_id: [0.0] * 384 for c in chunks}
        session = FakeSession()
        doc = DocumentMeta(
            doc_id=doc_id,
            title="Quy định tỷ lệ an toàn vốn",
            doc_type="Thông tư",
            source_file="41_2016_TT_NHNN.html",
            issue_number=doc_id,
        )

        load_document_chunks(session, doc, chunks, embeddings, "test-model")
        load_document_relationships(
            session, [DocRelationship(doc_id, "CAN_CU", "46/2010/QH12")]
        )

        queries = [q for q, _ in session.queries]
        self.assertTrue(any("MERGE (d:Document" in q for q in queries))
        self.assertTrue(any("PARENT_OF" in q for q in queries))
        self.assertTrue(any("PART_OF" in q for q in queries))
        self.assertTrue(any("NEXT" in q for q in queries))
        self.assertTrue(any("CAN_CU" in q for q in queries))

    def test_invalid_relationship_type_blocks_all_writes(self):
        session = FakeSession()
        with self.assertRaises(ValueError):
            load_document_relationships(
                session,
                [
                    DocRelationship("a", "CAN_CU", "b"),
                    DocRelationship("a", "SAI_LOAI", "c"),
                ],
            )
        # Validate trước khi ghi: không câu Cypher nào được chạy.
        self.assertEqual(session.queries, [])


if __name__ == "__main__":
    unittest.main()
