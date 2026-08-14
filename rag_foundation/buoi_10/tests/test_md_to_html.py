import unittest

from src.md_to_html import (
    _doc_type_from_suffix,
    build_html_document,
    extract_doc_info,
    markdown_to_html_body,
)

PREAMBLE = """# NGÂN HÀNG NHÀ NƯỚC VIỆT NAM

Số: 41 /2016/TT-NHNN

# Quy định tỷ lệ an toàn vốn đối với ngân hàng

Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12 ngày 16 tháng 6 năm 2010;

Căn cứ Luật các tổ chức tín dụng số 47/2010/QH12 ngày 16 tháng 6 năm 2010;

Căn cứ Nghị định số 156/2013/NĐ-CP ngày 11 tháng 11 năm 2013 của Chính phủ;

Theo đề nghị của Chánh Thanh tra, giám sát ngân hàng;

# Chương I
## Điều 1. Phạm vi điều chỉnh

1. Thông tư này quy định tỷ lệ an toàn vốn.
"""


class DocTypeSuffixTests(unittest.TestCase):
    def test_qh_prefix_is_luat(self):
        self.assertEqual(_doc_type_from_suffix("QH12"), "Luật")
        self.assertEqual(_doc_type_from_suffix("QH15"), "Luật")

    def test_known_suffixes(self):
        self.assertEqual(_doc_type_from_suffix("NĐ-CP"), "Nghị định")
        self.assertEqual(_doc_type_from_suffix("TT-NHNN"), "Thông tư")

    def test_unknown_suffix_returns_none_not_guess(self):
        self.assertIsNone(_doc_type_from_suffix("XYZ-ABC"))


class ExtractDocInfoTests(unittest.TestCase):
    def setUp(self):
        self.info = extract_doc_info(PREAMBLE, fallback_title="fallback")

    def test_extracts_own_issue_number(self):
        self.assertEqual(self.info.issue_number, "41/2016/TT-NHNN")
        self.assertEqual(self.info.doc_id, "41/2016/TT-NHNN")
        self.assertEqual(self.info.doc_type, "Thông tư")

    def test_extracts_title_from_quy_dinh_line(self):
        self.assertTrue(self.info.title.startswith("Quy định tỷ lệ an toàn vốn"))

    def test_extracts_three_can_cu_references(self):
        # Lỗi thật đã gặp: regex cũ không bắt được "QH12" vì \b cuối không khớp
        # giữa chữ H và số 1. Test này khoá lại lỗi đó.
        numbers = [r["issue_number"] for r in self.info.can_cu_refs]
        self.assertEqual(numbers, ["46/2010/QH12", "47/2010/QH12", "156/2013/NĐ-CP"])

    def test_can_cu_refs_have_doc_type(self):
        types = [r["doc_type"] for r in self.info.can_cu_refs]
        self.assertEqual(types, ["Luật", "Luật", "Nghị định"])

    def test_theo_de_nghi_line_is_not_a_reference(self):
        titles = " ".join(r["title"] for r in self.info.can_cu_refs)
        self.assertNotIn("Chánh Thanh tra", titles)

    def test_deduplicates_repeated_reference(self):
        md = PREAMBLE + "\nCăn cứ Luật các tổ chức tín dụng số 47/2010/QH12 ngày 16 tháng 6 năm 2010;\n"
        info = extract_doc_info(md, fallback_title="x")
        numbers = [r["issue_number"] for r in info.can_cu_refs]
        self.assertEqual(len(numbers), len(set(numbers)))


class MarkdownToHtmlTests(unittest.TestCase):
    def test_headings_mapped_by_level(self):
        html = markdown_to_html_body("# Chương I\n## Điều 1. ABC\n")
        self.assertIn("<h1>Chương I</h1>", html)
        self.assertIn("<h2>Điều 1. ABC</h2>", html)

    def test_plain_line_becomes_paragraph(self):
        html = markdown_to_html_body("Nội dung thường.")
        self.assertIn("<p>Nội dung thường.</p>", html)

    def test_bold_markers_stripped_but_text_kept(self):
        html = markdown_to_html_body("**VĂN PHÒNG CHÍNH PHỦ**")
        self.assertIn("<p>VĂN PHÒNG CHÍNH PHỦ</p>", html)

    def test_table_block_preserved_verbatim(self):
        md = "<table>\n  <tr><td>IC</td><td>8%</td></tr>\n</table>"
        html = markdown_to_html_body(md)
        self.assertIn("<table>", html)
        self.assertIn("<td>IC</td>", html)
        # Bảng KHÔNG được bọc trong <p> hay bị escape thành &lt;table&gt;
        self.assertNotIn("&lt;table", html)

    def test_unclosed_table_is_not_dropped(self):
        html = markdown_to_html_body("<table>\n<tr><td>còn dở</td></tr>")
        self.assertIn("còn dở", html)


class BuildHtmlDocumentTests(unittest.TestCase):
    def test_meta_tags_present(self):
        info = extract_doc_info(PREAMBLE, fallback_title="x")
        html = build_html_document(info, "<p>body</p>", "ghi chú nguồn")
        self.assertIn('name="doc-id" content="41/2016/TT-NHNN"', html)
        self.assertIn('name="doc-type" content="Thông tư"', html)
        self.assertIn('lang="vi"', html)


if __name__ == "__main__":
    unittest.main()
