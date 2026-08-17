#!/usr/bin/env python3
"""
Test cho pipeline retrieval Buoi 14.

Khong can mang, khong can API key, khong can Neo4j:
ep DENSE_BACKEND=lsa va RERANKER_BACKEND=fallback truoc khi import.

    python -m unittest discover -s tests -t .
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DENSE_BACKEND", "lsa")
os.environ.setdefault("RERANKER_BACKEND", "fallback")

import config  # noqa: E402
from src import bm25_retriever, corpus, hybrid_retriever, pipeline, reranker  # noqa: E402
from src.bm25_retriever import tokenize  # noqa: E402


class TestTokenizer(unittest.TestCase):
    def test_giu_ma_van_ban(self):
        toks = tokenize("Thông tư 01/2014/TT-NHNN")
        self.assertIn("01/2014/tt-nhnn", toks, "phai giu nguyen ma van ban")
        self.assertIn("nhnn", toks, "phai co ca manh de khop khi go thieu")

    def test_giu_so_dieu(self):
        toks = tokenize("Điều 72 quy định gì?")
        self.assertIn("điều_72", toks, "phai co token ghep dieu_<so>")

    def test_tieng_viet_co_dau(self):
        toks = tokenize("thẩm quyền phê duyệt")
        self.assertIn("thẩm", toks)
        self.assertIn("quyền", toks)


class TestCorpus(unittest.TestCase):
    def test_corpus_ton_tai_va_hop_le(self):
        chunks = corpus.load_chunks()
        self.assertGreater(len(chunks), 100)
        ids = [c["chunk_id"] for c in chunks]
        self.assertEqual(len(ids), len(set(ids)), "chunk_id phai duy nhat")
        for c in chunks[:50]:
            self.assertTrue(c["text"].strip(), "khong duoc co chunk rong")
            self.assertTrue(c["document_id"], "phai co document_id")

    def test_index_text_chua_so_hieu(self):
        """Loi da tung gap: chunk 'Dieu N' khong chua so hieu van ban cua chinh no."""
        for c in corpus.load_chunks():
            if c.get("so_ky_hieu") and c.get("article"):
                self.assertIn(c["so_ky_hieu"], corpus.index_text_of(c))
                break


class TestRetrievers(unittest.TestCase):
    QUERY_EXACT = "Thông tư 01/2014/TT-NHNN Điều 72 quy định nội dung gì?"
    QUERY_SEMANTIC = "Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức?"

    def test_bm25_tra_ve_ket_qua_va_citation(self):
        res = bm25_retriever.get_retriever().search(self.QUERY_EXACT, 5)
        self.assertTrue(res)
        for r in res:
            self.assertTrue(r["citation"], "citation khong duoc rong")
            self.assertTrue(r["chunk_id"])
            self.assertTrue(r["document_id"])
            self.assertEqual(r["retrieval_method"], "bm25")

    def test_bm25_uu_tien_dung_van_ban_khi_hoi_ma(self):
        res = bm25_retriever.get_retriever().search(self.QUERY_EXACT, 3)
        self.assertTrue(
            any(r["so_ky_hieu"] == "01/2014/TT-NHNN" for r in res),
            "hoi thang ma van ban thi top-3 phai co van ban do",
        )

    def test_hybrid_co_du_bm25_rank_va_dense_rank(self):
        """Loi 2 trong de bai: goi la Hybrid nhung thuc te chi chay Dense."""
        res = hybrid_retriever.get_retriever().search(
            self.QUERY_SEMANTIC, top_k=5, candidate_k=20
        )
        self.assertTrue(res)
        self.assertTrue(
            any(r.get("bm25_rank") for r in res), "phai co ung vien den tu BM25"
        )
        self.assertTrue(
            any(r.get("dense_rank") for r in res), "phai co ung vien den tu Dense"
        )
        for r in res:
            self.assertIn("rrf_score", r)

    def test_hybrid_khong_trung_chunk(self):
        res = hybrid_retriever.get_retriever().search(
            self.QUERY_SEMANTIC, top_k=10, candidate_k=20
        )
        ids = [r["chunk_id"] for r in res]
        self.assertEqual(len(ids), len(set(ids)), "Hybrid khong duoc tra ve chunk trung")


class TestReranker(unittest.TestCase):
    QUERY = "Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức?"

    def test_reranker_chi_nhan_candidate_khong_chay_toan_corpus(self):
        """Loi 4 trong de bai: rerank toan corpus."""
        cands = hybrid_retriever.get_retriever().candidates(self.QUERY, candidate_k=15)
        self.assertLessEqual(len(cands), 15)
        out = reranker.get_reranker().rerank(self.QUERY, cands, top_k=5)
        self.assertLessEqual(len(out), 5)
        kept = {r["chunk_id"] for r in out}
        self.assertTrue(kept.issubset({c["chunk_id"] for c in cands}),
                        "ket qua rerank phai nam trong tap candidate")

    def test_rerank_khong_phai_sort_lai_hybrid_score(self):
        """Loi 3 trong de bai: goi la rerank nhung chi sort lai hybrid_score."""
        cands = hybrid_retriever.get_retriever().candidates(self.QUERY, candidate_k=20)
        out = reranker.get_reranker().rerank(self.QUERY, cands, top_k=10)
        hybrid_order = [c["chunk_id"] for c in cands[:10]]
        rerank_order = [r["chunk_id"] for r in out]
        self.assertNotEqual(
            hybrid_order, rerank_order,
            "rerank_score phai la tin hieu doc lap, khong the trung y het thu tu RRF",
        )

    def test_khong_mat_citation_sau_rerank(self):
        """Loi 5 trong de bai: citation bi mat sau Hybrid/Rerank."""
        out = pipeline.retrieve(self.QUERY, "hybrid_rerank", top_k=5, candidate_k=20)
        for r in out["results"]:
            self.assertTrue(r["chunk_id"])
            self.assertTrue(r["document_id"])
            self.assertTrue(r["citation"], "citation phai con nguyen sau rerank")


class TestPipeline(unittest.TestCase):
    def test_du_bon_method(self):
        self.assertEqual(
            set(pipeline.METHODS), {"bm25", "dense", "hybrid", "hybrid_rerank"}
        )

    def test_moi_method_deu_chay_va_dung_schema(self):
        for m in pipeline.METHODS:
            out = pipeline.retrieve("quy định về kiểm toán độc lập", m, top_k=3)
            self.assertTrue(out["results"], f"method {m} khong tra ve ket qua")
            for r in out["results"]:
                for field in ("rank", "chunk_id", "document_id", "text",
                              "citation", "retrieval_method"):
                    self.assertIn(field, r, f"{m} thieu truong {field}")

    def test_method_sai_bao_loi(self):
        with self.assertRaises(ValueError):
            pipeline.retrieve("abc", "khong_ton_tai")

    def test_backend_info_trung_thuc(self):
        info = pipeline.backend_info()
        self.assertEqual(info["dense_backend"], "lsa")
        self.assertFalse(info["dense_is_neural"], "LSA khong duoc bao la neural")
        self.assertFalse(info["rerank_is_neural"], "fallback khong duoc bao la neural")


class TestAnToanDuLieu(unittest.TestCase):
    def test_khong_ghi_vao_thu_muc_nguon(self):
        """Moi output phai nam trong buoi_14/, khong dung toi KB_DIR."""
        for p in (config.CHUNKS_CSV, config.QUESTIONS_CSV, config.OUTPUTS_DIR):
            self.assertTrue(
                str(p).startswith(str(config.BASE_DIR)),
                f"{p} phai nam trong {config.BASE_DIR}",
            )
        self.assertFalse(
            str(config.KB_DIR).startswith(str(config.BASE_DIR)),
            "KB_DIR la du lieu nguon ben ngoai, chi doc",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
