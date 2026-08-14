import unittest

from src.gemini_qa import (
    NO_CONTEXT_ANSWER_HINT,
    answer_question,
    build_system_prompt,
    build_user_prompt,
)
from src.graph_search import ContextChunk


def _chunk(chunk_id="c1", hop=0, heading="Điều 1. Test", doc_id="41/2016/TT-NHNN", text="nội dung mẫu"):
    return ContextChunk(
        chunk_id=chunk_id, text=text, heading=heading, doc_id=doc_id,
        level="dieu", score=0.87, hop=hop,
    )


class BuildSystemPromptTests(unittest.TestCase):
    def test_mentions_graph_schema_labels(self):
        prompt = build_system_prompt()
        for token in ("Document", "Chunk", "PART_OF", "PARENT_OF", "CAN_CU", "THAY_THE", "HOP_NHAT"):
            self.assertIn(token, prompt)

    def test_states_no_hallucination_rule(self):
        prompt = build_system_prompt()
        self.assertIn(NO_CONTEXT_ANSWER_HINT, prompt)


class BuildUserPromptTests(unittest.TestCase):
    def test_includes_question_and_chunk_text(self):
        prompt = build_user_prompt("Điều 1 quy định gì?", [_chunk()])
        self.assertIn("Điều 1 quy định gì?", prompt)
        self.assertIn("nội dung mẫu", prompt)
        self.assertIn("hop=0", prompt)
        self.assertIn("41/2016/TT-NHNN", prompt)

    def test_empty_chunks_says_no_match(self):
        prompt = build_user_prompt("câu hỏi bất kỳ", [])
        self.assertIn("không tìm thấy đoạn văn bản nào liên quan", prompt)

    def test_chunk_without_heading_uses_placeholder(self):
        prompt = build_user_prompt("q", [_chunk(heading=None)])
        self.assertIn("không có tiêu đề", prompt)


class AnswerQuestionTests(unittest.TestCase):
    def test_calls_call_fn_with_system_and_user_prompt(self):
        captured = {}

        def fake_call(system_prompt: str, user_prompt: str) -> str:
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            return "câu trả lời giả"

        result = answer_question("Điều 1 nói gì?", [_chunk()], fake_call)
        self.assertEqual(result, "câu trả lời giả")
        self.assertIn("Document", captured["system_prompt"])
        self.assertIn("Điều 1 nói gì?", captured["user_prompt"])


if __name__ == "__main__":
    unittest.main()
