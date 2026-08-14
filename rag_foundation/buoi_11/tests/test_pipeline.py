import unittest

from src.pipeline import (
    COMPARE_HOPS,
    TEST_QUESTIONS,
    _format_sources,
    _require_vector_index,
    _run_one_question,
    build_arg_parser,
)
from src.graph_search import ContextChunk, VECTOR_INDEX_NAME

from .fakes import FakeSession


class FakeEmbedder:
    """Vector cố định chiều 4, deterministic — không tải model thật."""

    def __call__(self, texts):
        return [[float(len(t)), 0.0, 0.0, 0.0] for t in texts]


class TestQuestionsTests(unittest.TestCase):
    def test_exactly_five_questions_from_assignment(self):
        self.assertEqual(len(TEST_QUESTIONS), 5)

    def test_compare_hops_matches_assignment(self):
        self.assertEqual(COMPARE_HOPS, (0, 1, 2))

    def test_question_four_mentions_thong_tu_41(self):
        # Câu hỏi duy nhất khớp được với dữ liệu thật hiện có (SPEC mục 6).
        self.assertIn("41/2016/TT-NHNN", TEST_QUESTIONS[3])


class FormatSourcesTests(unittest.TestCase):
    def test_empty_list(self):
        self.assertIn("không có nguồn", _format_sources([]))

    def test_lists_hop_score_doc_id(self):
        chunk = ContextChunk(
            chunk_id="c1", text="t", heading="Điều 1.", doc_id="41/2016/TT-NHNN",
            level="dieu", score=0.876, hop=1,
        )
        formatted = _format_sources([chunk])
        self.assertIn("hop=1", formatted)
        self.assertIn("0.8760", formatted)
        self.assertIn("41/2016/TT-NHNN", formatted)


class RequireVectorIndexTests(unittest.TestCase):
    def test_raises_system_exit_when_missing(self):
        session = FakeSession()
        session.index_names = []
        with self.assertRaises(SystemExit):
            _require_vector_index(session)

    def test_passes_silently_when_present(self):
        session = FakeSession()
        session.index_names = [VECTOR_INDEX_NAME]
        _require_vector_index(session)  # không raise


class RunOneQuestionTests(unittest.TestCase):
    def test_returns_chunks_and_answer_using_fakes(self):
        session = FakeSession()
        session.direct_rows = [
            {"chunk_id": "c1", "text": "nội dung", "heading": "Điều 1.", "doc_id": "d1", "level": "dieu", "score": 0.9}
        ]

        def fake_gemini(system_prompt: str, user_prompt: str) -> str:
            return "trả lời giả từ Gemini"

        chunks, answer = _run_one_question(
            session, FakeEmbedder(), fake_gemini, "câu hỏi test", hops=0,
            top_k_direct=5, top_k_per_hop=2,
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(answer, "trả lời giả từ Gemini")


class ArgParserTests(unittest.TestCase):
    def test_has_three_subcommands(self):
        parser = build_arg_parser()
        args = parser.parse_args(["ask", "câu hỏi?", "--hops", "2"])
        self.assertEqual(args.command, "ask")
        self.assertEqual(args.hops, 2)

    def test_compare_default_output_path(self):
        parser = build_arg_parser()
        args = parser.parse_args(["compare"])
        self.assertEqual(args.output, "reports/qa_comparison.md")

    def test_setup_index_subcommand_exists(self):
        parser = build_arg_parser()
        args = parser.parse_args(["setup-index"])
        self.assertEqual(args.command, "setup-index")


if __name__ == "__main__":
    unittest.main()
