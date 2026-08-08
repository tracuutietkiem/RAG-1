"""tests/test_multiquery.py — Test Multi-query Generator (Bước 04).

Nguyên tắc: offline hoàn toàn. Gemini luôn được thay bằng `query_generator_fn`
giả lập — không gọi mạng, không đọc `.env` thật, không tải model.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import advanced_rag as ar  # noqa: E402
import hierarchical_rag as hr  # noqa: E402
import rag  # noqa: E402

from test_hierarchy import write_env  # noqa: E402  (dùng lại helper)


class _FakeGenerator:
    """Generator giả lập, đếm số lần được gọi để kiểm tra 'đúng một call'."""

    def __init__(self, payload=None, raises=None):
        self.payload = payload if payload is not None else {
            "queries": [
                {"text": "thuật ngữ pháp lý chính xác cho câu hỏi", "focus": "exact_legal_terms"},
                {"text": "cách diễn đạt tương đương của câu hỏi", "focus": "paraphrase"},
                {"text": "khía cạnh còn thiếu của câu hỏi", "focus": "missing_aspect"},
            ]
        }
        self.raises = raises
        self.calls = 0

    def __call__(self, question, config, hcfg):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.payload


class MultiQueryTestBase(unittest.TestCase):
    def setUp(self):
        hr.clear_query_cache()
        self.work = Path(tempfile.mkdtemp())
        env = write_env(self.work / ".env")
        self.config = ar.load_advanced_config(env)
        self.hcfg = hr.load_hierarchy_config(env)

    def tearDown(self):
        hr.clear_query_cache()
        shutil.rmtree(self.work, ignore_errors=True)

    def expand(self, question="Điều 7 quy định vốn tự có gồm những gì?", gen=None, **kw):
        gen = gen or _FakeGenerator()
        return hr.expand_query(question, self.config, self.hcfg, query_generator_fn=gen, **kw), gen


# ---------------------------------------------------------------------------
# 1. Q0 preservation
# ---------------------------------------------------------------------------


class Q0Tests(MultiQueryTestBase):
    def test_q0_always_first_and_unchanged(self):
        q = "Điều 7 quy định vốn tự có gồm những gì?"
        res, _ = self.expand(q)
        self.assertEqual(res["queries"][0]["query_id"], "Q0")
        self.assertEqual(res["queries"][0]["text"], q)
        self.assertEqual(res["queries"][0]["origin"], "original")
        self.assertEqual(res["queries"][0]["focus"], "original_intent")

    def test_q0_trimmed_and_nfc(self):
        import unicodedata

        raw = "  " + unicodedata.normalize("NFD", "Điều 7 quy định gì?") + "  "
        res, _ = self.expand(raw)
        self.assertEqual(res["queries"][0]["text"], "Điều 7 quy định gì?")

    def test_q0_survives_generation_failure(self):
        gen = _FakeGenerator(raises=hr.QueryGenerationError("API sập"))
        res, _ = self.expand(gen=gen)
        self.assertEqual(res["status"], "query_generation_unavailable")
        self.assertEqual(len(res["queries"]), 1)
        self.assertEqual(res["queries"][0]["query_id"], "Q0")

    def test_empty_question_raises(self):
        for bad in ("", "   ", None, 123):
            with self.subTest(q=bad):
                with self.assertRaises(rag.DataError):
                    hr.expand_query(bad, self.config, self.hcfg, query_generator_fn=_FakeGenerator())

    def test_too_long_question_raises(self):
        with self.assertRaises(rag.DataError):
            hr.expand_query("x" * 3000, self.config, self.hcfg, query_generator_fn=_FakeGenerator())


# ---------------------------------------------------------------------------
# 2. Schema validation
# ---------------------------------------------------------------------------


class SchemaTests(MultiQueryTestBase):
    def test_missing_queries_key_raises(self):
        gen = _FakeGenerator(payload={"wrong": []})
        with self.assertRaises(hr.QueryGenerationError):
            hr.expand_query("Câu hỏi", self.config, self.hcfg, query_generator_fn=gen)

    def test_non_dict_payload_raises(self):
        gen = _FakeGenerator(payload=["a", "b"])
        with self.assertRaises(hr.QueryGenerationError):
            hr.expand_query("Câu hỏi", self.config, self.hcfg, query_generator_fn=gen)

    def test_item_without_text_dropped(self):
        gen = _FakeGenerator(payload={"queries": [
            {"focus": "paraphrase"},
            {"text": "truy vấn hợp lệ", "focus": "paraphrase"},
        ]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(len(res["queries"]), 2, "Q0 + 1 variant hợp lệ")
        self.assertEqual(res["dropped_invalid_count"], 1)

    def test_invalid_focus_defaults_to_paraphrase(self):
        gen = _FakeGenerator(payload={"queries": [{"text": "truy vấn", "focus": "bịa"}]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(res["queries"][1]["focus"], "paraphrase")
        self.assertTrue(any("focus" in w for w in res["warnings"]))

    def test_result_has_full_schema(self):
        res, _ = self.expand()
        for key in ("original_question", "queries", "model", "generation_latency_ms",
                    "cache_hit", "dropped_duplicate_count", "status", "warnings"):
            self.assertIn(key, res)

    def test_no_answer_field_leaks_into_result(self):
        """Model có trả thêm field lạ cũng không được lọt vào query set."""
        gen = _FakeGenerator(payload={"queries": [
            {"text": "truy vấn", "focus": "paraphrase", "answer": "Vốn tự có là...", "citation": "[E1]"}
        ]})
        res, _ = self.expand(gen=gen)
        v = res["queries"][1]
        self.assertEqual(set(v.keys()), {"query_id", "text", "origin", "focus"})


# ---------------------------------------------------------------------------
# 3. Limits, NFC, dedupe
# ---------------------------------------------------------------------------


class LimitTests(MultiQueryTestBase):
    def test_respects_multi_query_count(self):
        gen = _FakeGenerator(payload={"queries": [
            {"text": f"truy vấn số {i}", "focus": "paraphrase"} for i in range(10)
        ]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(len(res["queries"]), 1 + self.hcfg.multi_query_count)

    def test_too_long_variant_dropped(self):
        gen = _FakeGenerator(payload={"queries": [
            {"text": "x" * (self.hcfg.multi_query_max_chars + 1), "focus": "paraphrase"},
            {"text": "truy vấn ngắn hợp lệ", "focus": "paraphrase"},
        ]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(len(res["queries"]), 2)
        self.assertEqual(res["dropped_invalid_count"], 1)

    def test_duplicate_variants_removed(self):
        gen = _FakeGenerator(payload={"queries": [
            {"text": "Điều kiện vay vốn là gì", "focus": "paraphrase"},
            {"text": "  điều kiện vay vốn là gì!!  ", "focus": "paraphrase"},
            {"text": "ĐIỀU KIỆN VAY VỐN LÀ GÌ?", "focus": "exact_legal_terms"},
        ]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(len(res["queries"]), 2, "3 biến thể giống nhau -> chỉ giữ 1")
        self.assertEqual(res["dropped_duplicate_count"], 2)

    def test_variant_equal_to_q0_removed(self):
        q = "Điều 7 quy định gì?"
        gen = _FakeGenerator(payload={"queries": [
            {"text": q, "focus": "paraphrase"},
            {"text": "cách hỏi khác hoàn toàn", "focus": "paraphrase"},
        ]})
        res, _ = self.expand(q, gen=gen)
        self.assertEqual(len(res["queries"]), 2)
        self.assertEqual(res["dropped_duplicate_count"], 1)

    def test_fewer_valid_queries_no_fake_created(self):
        gen = _FakeGenerator(payload={"queries": [{"text": "chỉ một truy vấn", "focus": "paraphrase"}]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(len(res["queries"]), 2, "KHÔNG được tạo query giả để đủ số lượng")
        self.assertEqual(res["status"], "ready")

    def test_all_variants_invalid_gives_unavailable(self):
        gen = _FakeGenerator(payload={"queries": [{"text": "   ", "focus": "paraphrase"}]})
        res, _ = self.expand(gen=gen)
        self.assertEqual(res["status"], "query_generation_unavailable")
        self.assertEqual(len(res["queries"]), 1)

    def test_deterministic_query_ids(self):
        res, _ = self.expand()
        ids = [q["query_id"] for q in res["queries"]]
        self.assertEqual(ids, ["Q0", "Q1", "Q2", "Q3"])


# ---------------------------------------------------------------------------
# 4. Legal reference
# ---------------------------------------------------------------------------


class LegalReferenceTests(MultiQueryTestBase):
    def test_extract_refs(self):
        refs = hr.extract_legal_refs("Điều 7 và Khoản 2 Điểm a của Thông tư 41/2016/TT-NHNN năm 2016")
        self.assertIn("điều 7", refs)
        self.assertIn("khoản 2", refs)
        self.assertIn("2016", refs)

    def test_invented_article_number_dropped(self):
        """Model bịa 'Điều 99' không có trong câu hỏi -> phải loại."""
        gen = _FakeGenerator(payload={"queries": [
            {"text": "Điều 99 quy định vốn tự có", "focus": "exact_legal_terms"},
            {"text": "cấu phần của vốn tự có", "focus": "paraphrase"},
        ]})
        res, _ = self.expand("Điều 7 quy định vốn tự có gồm những gì?", gen=gen)
        texts = [q["text"] for q in res["queries"]]
        self.assertNotIn("Điều 99 quy định vốn tự có", texts)
        self.assertEqual(res["dropped_invalid_count"], 1)
        self.assertTrue(any("bịa thêm" in w for w in res["warnings"]))

    def test_original_reference_allowed_in_variant(self):
        gen = _FakeGenerator(payload={"queries": [
            {"text": "Điều 7 vốn tự có cấu phần", "focus": "exact_legal_terms"},
        ]})
        res, _ = self.expand("Điều 7 quy định vốn tự có gồm những gì?", gen=gen)
        self.assertEqual(len(res["queries"]), 2, "giữ nguyên Điều 7 là hợp lệ")

    def test_warning_when_no_variant_preserves_reference(self):
        gen = _FakeGenerator(payload={"queries": [
            {"text": "vốn tự có gồm những gì", "focus": "paraphrase"},
        ]})
        res, _ = self.expand("Điều 7 quy định vốn tự có gồm những gì?", gen=gen)
        self.assertTrue(any("giữ reference" in w for w in res["warnings"]))

    def test_question_without_reference_no_warning(self):
        gen = _FakeGenerator(payload={"queries": [{"text": "vốn tự có là gì", "focus": "paraphrase"}]})
        res, _ = self.expand("Vốn tự có là gì?", gen=gen)
        self.assertFalse(any("giữ reference" in w for w in res["warnings"]))


# ---------------------------------------------------------------------------
# 5. Một call + cache
# ---------------------------------------------------------------------------


class CallAndCacheTests(MultiQueryTestBase):
    def test_exactly_one_generator_call(self):
        _, gen = self.expand()
        self.assertEqual(gen.calls, 1, "một lần expansion = đúng MỘT API call")

    def test_cache_hit_does_not_call_again(self):
        q = "Điều 7 quy định vốn tự có gồm những gì?"
        gen = _FakeGenerator()
        hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen)
        res2 = hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen)
        self.assertEqual(gen.calls, 1, "lần hai phải lấy từ cache")
        self.assertTrue(res2["cache_hit"])

    def test_cache_miss_for_different_question(self):
        gen = _FakeGenerator()
        hr.expand_query("Câu hỏi một", self.config, self.hcfg, query_generator_fn=gen)
        hr.expand_query("Câu hỏi hai", self.config, self.hcfg, query_generator_fn=gen)
        self.assertEqual(gen.calls, 2)

    def test_cache_can_be_disabled(self):
        gen = _FakeGenerator()
        q = "Cùng một câu hỏi"
        hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen, use_cache=False)
        hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen, use_cache=False)
        self.assertEqual(gen.calls, 2)

    def test_failed_generation_not_cached(self):
        gen_fail = _FakeGenerator(raises=hr.QueryGenerationError("lỗi tạm thời"))
        q = "Câu hỏi thử"
        hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen_fail)
        gen_ok = _FakeGenerator()
        res = hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen_ok)
        self.assertEqual(gen_ok.calls, 1, "lỗi không được cache")
        self.assertEqual(res["status"], "ready")

    def test_cache_returns_copy_not_reference(self):
        q = "Câu hỏi bất kỳ"
        gen = _FakeGenerator()
        r1 = hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen)
        r1["queries"].append({"query_id": "HACK"})
        r2 = hr.expand_query(q, self.config, self.hcfg, query_generator_fn=gen)
        self.assertNotIn("HACK", [x.get("query_id") for x in r2["queries"]])


# ---------------------------------------------------------------------------
# 6. Không gọi mạng / không dùng key thật
# ---------------------------------------------------------------------------


class OfflineTests(MultiQueryTestBase):
    def test_no_network_in_tests(self):
        """Generator thật không bao giờ được gọi khi đã tiêm fake."""
        calls = []
        original = hr._default_query_generator
        try:
            hr._default_query_generator = lambda *a, **kw: calls.append(1)
            self.expand()
            self.assertEqual(calls, [], "phải dùng generator được tiêm, không gọi Gemini")
        finally:
            hr._default_query_generator = original

    def test_missing_api_key_gives_explicit_status(self):
        env = write_env(self.work / "nokey.env", GEMINI_API_KEY="")
        config = ar.load_advanced_config(env)
        hcfg = hr.load_hierarchy_config(env)
        res = hr.expand_query("Câu hỏi", config, hcfg)  # dùng generator thật
        self.assertEqual(res["status"], "query_generation_unavailable")
        self.assertTrue(any("GEMINI_API_KEY" in w for w in res["warnings"]))
        self.assertEqual(len(res["queries"]), 1, "Q0 vẫn còn")

    def test_prompt_contains_no_answer_instruction(self):
        prompt = hr.build_query_prompt("Câu hỏi mẫu", 3, 300)
        self.assertIn("KHÔNG trả lời", prompt)
        self.assertIn("KHÔNG được bịa thêm số Điều", prompt)

    def test_schema_only_allows_text_and_focus(self):
        props = hr.QUERY_VARIANT_SCHEMA["properties"]["queries"]["items"]["properties"]
        self.assertEqual(set(props.keys()), {"text", "focus"},
                         "model KHÔNG được phép trả answer/citation/query_id")


if __name__ == "__main__":
    unittest.main()
