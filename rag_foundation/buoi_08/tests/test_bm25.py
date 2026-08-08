"""tests/test_bm25.py — Test tokenizer và BM25 lexical retrieval (Bước 04).

Chạy: <PYTHON> -m unittest discover -s rag_foundation/buoi_08/tests -v

Nguyên tắc (SPEC_buoi_08.md mục 11): `unittest`, không Internet, không gọi
Gemini, không tải model Hugging Face, không đụng storage thật. Toàn bộ test
trong file này chỉ dùng dữ liệu mô phỏng trong bộ nhớ hoặc fixture tĩnh.
"""

from __future__ import annotations

import json
import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import advanced_rag as ar  # noqa: E402
import rag  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture_chunks(strategy: str = "hierarchical") -> list[dict]:
    chunks, _stats = rag.load_chunks(input_dir=FIXTURE_DIR, strategy=strategy)
    return chunks


def _make_chunk(chunk_id: str, text: str, page: int = 1) -> dict:
    return {
        "chunk_id": chunk_id,
        "strategy": "hierarchical",
        "source": "fixture_mo_phong.pdf",
        "page_start": page,
        "page_end": page,
        "text": text,
    }


class TokenizeViLegalTests(unittest.TestCase):
    def test_input_must_be_string(self):
        for bad in (None, 123, ["a"], {"a": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(rag.DataError):
                    ar.tokenize_vi_legal(bad)

    def test_keeps_vietnamese_diacritics(self):
        tokens = ar.tokenize_vi_legal("cơ cấu lại thời hạn trả nợ")
        self.assertEqual(tokens, ["cơ", "cấu", "lại", "thời", "hạn", "trả", "nợ"])

    def test_keeps_dieu_khoan_numbers(self):
        tokens = ar.tokenize_vi_legal("Điều 7, Khoản 2")
        for expected in ("điều", "7", "khoản", "2"):
            self.assertIn(expected, tokens)

    def test_unicode_nfc_normalization(self):
        """Cùng một chữ mã hoá NFD và NFC phải cho token giống hệt nhau."""
        text_nfc = unicodedata.normalize("NFC", "Điều")
        text_nfd = unicodedata.normalize("NFD", "Điều")
        self.assertNotEqual(text_nfc, text_nfd, "Chuỗi test phải khác nhau ở dạng mã hoá")
        self.assertEqual(ar.tokenize_vi_legal(text_nfc), ar.tokenize_vi_legal(text_nfd))

    def test_casefold_applied(self):
        self.assertEqual(ar.tokenize_vi_legal("ĐIỀU"), ar.tokenize_vi_legal("điều"))

    def test_punctuation_and_whitespace_removed(self):
        tokens = ar.tokenize_vi_legal("  Điều 7.  Khoản 2;  (a)  ")
        self.assertNotIn("", tokens)
        self.assertNotIn(".", tokens)
        self.assertNotIn(";", tokens)
        self.assertEqual(tokens, ["điều", "7", "khoản", "2", "a"])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(ar.tokenize_vi_legal("   "), [])

    def test_no_stemming_applied(self):
        """Không stemming: từ giữ nguyên hình thái, không bị cắt đuôi."""
        self.assertEqual(ar.tokenize_vi_legal("khoản khoảng"), ["khoản", "khoảng"])

    def test_same_function_used_for_corpus_and_query(self):
        """Corpus và query phải đi qua đúng cùng một hàm preprocessing."""
        text = "Điều 7. Cơ cấu lại thời hạn trả nợ"
        chunks = [_make_chunk("c1", text)]
        index = ar.build_bm25_index(chunks)
        self.assertEqual(index.tokenized_corpus[0], ar.tokenize_vi_legal(text))


class BM25IndexTests(unittest.TestCase):
    def test_empty_corpus_raises(self):
        with self.assertRaises(rag.DataError):
            ar.build_bm25_index([])

    def test_non_list_raises(self):
        with self.assertRaises(rag.DataError):
            ar.build_bm25_index("khong phai list")

    def test_chunk_with_no_token_raises(self):
        chunks = [_make_chunk("c1", "noi dung binh thuong"), _make_chunk("c2", "...")]
        with self.assertRaises(rag.DataError):
            ar.build_bm25_index(chunks)

    def test_index_size_matches_corpus(self):
        chunks = _load_fixture_chunks()
        index = ar.build_bm25_index(chunks)
        self.assertEqual(index.size, len(chunks))
        self.assertEqual(len(index.tokenized_corpus), len(chunks))

    def test_source_chunks_not_mutated(self):
        chunks = _load_fixture_chunks()
        before = json.dumps(chunks, sort_keys=True, ensure_ascii=False)
        index = ar.build_bm25_index(chunks)
        ar.bm25_search("Điều 7 quy định gì?", index, 5)
        after = json.dumps(chunks, sort_keys=True, ensure_ascii=False)
        self.assertEqual(before, after, "BM25 không được sửa chunk nguồn")


class BM25SearchTests(unittest.TestCase):
    def setUp(self):
        self.chunks = _load_fixture_chunks()
        self.index = ar.build_bm25_index(self.chunks)

    def test_empty_question_fails(self):
        for bad in ("", "   ", "!!! ,,, ---"):
            with self.subTest(question=bad):
                with self.assertRaises(rag.DataError):
                    ar.bm25_search(bad, self.index, 5)

    def test_invalid_candidate_k_fails(self):
        for bad in (0, -1, 1.5, True, "5"):
            with self.subTest(candidate_k=bad):
                with self.assertRaises(rag.DataError):
                    ar.bm25_search("Điều 7 quy định gì?", self.index, bad)

    def test_exact_legal_term_ranked_above_unrelated(self):
        """Chunk chứa đúng 'Điều 7' phải xếp trên đoạn ngoài phạm vi."""
        results = ar.bm25_search("Điều 7 cơ cấu lại thời hạn trả nợ", self.index, 8)
        ranks = {r["chunk_id"]: r["bm25_rank"] for r in results}
        # adv_h_0001 và adv_h_0002 là 2 chunk "Điều 7"; adv_h_0008 là decoy máy cà phê
        self.assertLess(ranks["adv_h_0001"], ranks["adv_h_0008"])
        self.assertLess(ranks["adv_h_0002"], ranks["adv_h_0008"])

    def test_exact_dieu_number_matters(self):
        """Hỏi 'Điều 12' phải ưu tiên chunk Điều 12 hơn chunk Điều 7."""
        results = ar.bm25_search("Điều 12 phân loại nợ", self.index, 8)
        ranks = {r["chunk_id"]: r["bm25_rank"] for r in results}
        self.assertLess(min(ranks["adv_h_0004"], ranks["adv_h_0005"]), ranks["adv_h_0001"])

    def test_candidate_k_larger_than_corpus_is_clamped(self):
        results = ar.bm25_search("Điều 7 quy định gì?", self.index, 9999)
        self.assertEqual(len(results), self.index.size)

    def test_candidate_k_smaller_than_corpus(self):
        results = ar.bm25_search("Điều 7 quy định gì?", self.index, 3)
        self.assertEqual(len(results), 3)

    def test_ranks_are_sequential_from_one(self):
        results = ar.bm25_search("Điều 7 quy định gì?", self.index, 5)
        self.assertEqual([r["bm25_rank"] for r in results], [1, 2, 3, 4, 5])

    def test_scores_are_non_increasing(self):
        results = ar.bm25_search("phân loại nợ trích lập dự phòng", self.index, 8)
        scores = [r["bm25_score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_zero_score_candidates_still_returned(self):
        """
        Không lọc bỏ candidate chỉ vì score = 0 — vẫn trả đủ top-k.

        Query "máy pha cà phê" chỉ khớp đúng chunk decoy ngoài phạm vi
        (adv_h_0008); toàn bộ chunk còn lại có BM25 score = 0 nhưng vẫn phải
        nằm trong kết quả trả về (giữ nguyên score, để tầng RRF/rerank phía
        sau tự quyết định).
        """
        results = ar.bm25_search("máy pha cà phê", self.index, self.index.size)
        self.assertEqual(len(results), self.index.size)
        zero_score = [r for r in results if r["bm25_score"] == 0.0]
        self.assertTrue(zero_score, "Query này phải tạo ra chunk có score 0")
        self.assertEqual(results[0]["chunk_id"], "adv_h_0008", "Chunk khớp từ khoá phải đứng đầu")

    def test_tie_break_deterministic_by_chunk_id(self):
        """Các chunk cùng score phải luôn xếp theo chunk_id, ổn định giữa các lần chạy."""
        chunks = [
            _make_chunk("c_zzz", "noi dung giong het nhau ve nghiep vu"),
            _make_chunk("c_aaa", "noi dung giong het nhau ve nghiep vu"),
            _make_chunk("c_mmm", "noi dung giong het nhau ve nghiep vu"),
        ]
        index = ar.build_bm25_index(chunks)
        first = [r["chunk_id"] for r in ar.bm25_search("nghiep vu", index, 3)]
        second = [r["chunk_id"] for r in ar.bm25_search("nghiep vu", index, 3)]
        self.assertEqual(first, second, "Kết quả phải deterministic")
        self.assertEqual(first, ["c_aaa", "c_mmm", "c_zzz"], "Tie-break phải theo chunk_id tăng dần")

    def test_output_schema_complete(self):
        results = ar.bm25_search("Điều 7 quy định gì?", self.index, 3)
        required = {"chunk_id", "text", "source", "page_start", "page_end", "bm25_rank", "bm25_score"}
        for r in results:
            self.assertTrue(required.issubset(r.keys()), f"Thiếu field: {required - set(r.keys())}")
            self.assertIsInstance(r["bm25_score"], float)
            self.assertIsInstance(r["bm25_rank"], int)

    def test_metadata_matches_source_chunks(self):
        by_id = {c["chunk_id"]: c for c in self.chunks}
        for r in ar.bm25_search("Điều 12 phân loại nợ", self.index, 5):
            src = by_id[r["chunk_id"]]
            self.assertEqual(r["source"], src["source"])
            self.assertEqual(r["page_start"], src["page_start"])
            self.assertEqual(r["page_end"], src["page_end"])
            self.assertEqual(r["text"], src["text"])


class NoExternalCallTests(unittest.TestCase):
    """BM25 stage phải hoàn toàn cục bộ: không Gemini, không Chroma, không model."""

    def test_bm25_does_not_call_gemini_or_chroma_or_reranker(self):
        calls = []

        def _boom(*args, **kwargs):
            calls.append(args)
            raise AssertionError("BM25 stage không được gọi API/Chroma/model")

        original = {
            "embed_documents": rag.embed_documents,
            "embed_query": rag.embed_query,
            "generate_answer": rag.generate_answer,
            "_chroma_client": rag._chroma_client,
            "_default_gemini_client": rag._default_gemini_client,
        }
        try:
            rag.embed_documents = _boom
            rag.embed_query = _boom
            rag.generate_answer = _boom
            rag._chroma_client = _boom
            rag._default_gemini_client = _boom

            chunks = _load_fixture_chunks()
            index = ar.build_bm25_index(chunks)
            results = ar.bm25_search("Điều 7 quy định gì?", index, 5)
            self.assertEqual(len(results), 5)
            self.assertEqual(calls, [], "Không được có lời gọi ra ngoài")
        finally:
            for name, fn in original.items():
                setattr(rag, name, fn)

    def test_transformers_and_torch_not_imported_by_bm25(self):
        """Import advanced_rag + chạy BM25 không được kéo theo model runtime."""
        chunks = _load_fixture_chunks()
        index = ar.build_bm25_index(chunks)
        ar.bm25_search("Điều 7 quy định gì?", index, 3)
        # transformers/torch có thể đã được import bởi test khác trong cùng
        # process; điều bắt buộc là advanced_rag KHÔNG tự import chúng ở
        # module level (kiểm tra qua source, không qua sys.modules).
        source = (Path(__file__).resolve().parent.parent / "advanced_rag.py").read_text(encoding="utf-8")
        module_level = [
            line
            for line in source.splitlines()
            if (line.startswith("import ") or line.startswith("from "))
            and ("torch" in line or "transformers" in line)
        ]
        self.assertEqual(module_level, [], f"Không được import model runtime ở module level: {module_level}")


if __name__ == "__main__":
    unittest.main()
