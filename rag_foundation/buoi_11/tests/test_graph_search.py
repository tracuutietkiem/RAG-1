import unittest

from src.graph_search import (
    VECTOR_INDEX_NAME,
    SearchConfig,
    chunks_for_document_by_similarity,
    create_vector_index,
    has_vector_index,
    neighbor_documents,
    search_context,
    vector_search,
)

from .fakes import FakeSession


class HasVectorIndexTests(unittest.TestCase):
    def test_true_when_index_present(self):
        session = FakeSession()
        session.index_names = ["document_doc_id", VECTOR_INDEX_NAME]
        self.assertTrue(has_vector_index(session))

    def test_false_when_index_missing(self):
        session = FakeSession()
        session.index_names = ["document_doc_id"]
        self.assertFalse(has_vector_index(session))


class CreateVectorIndexTests(unittest.TestCase):
    def test_runs_create_statement(self):
        session = FakeSession()
        create_vector_index(session)
        self.assertEqual(len(session.queries), 1)
        self.assertIn("CREATE VECTOR INDEX", session.queries[0][0])


class VectorSearchTests(unittest.TestCase):
    def test_passes_k_and_query_vector(self):
        session = FakeSession()
        session.direct_rows = [
            {"chunk_id": "c1", "text": "t1", "heading": "Điều 1.", "doc_id": "d1", "level": "dieu", "score": 0.9}
        ]
        rows = vector_search(session, [0.1, 0.2], k=5)
        self.assertEqual(rows, session.direct_rows)
        _, params = session.queries[0]
        self.assertEqual(params["k"], 5)
        self.assertEqual(params["query_vector"], [0.1, 0.2])


class NeighborDocumentsTests(unittest.TestCase):
    def test_hops_zero_returns_empty_without_query(self):
        session = FakeSession()
        result = neighbor_documents(session, ["d1"], hops=0)
        self.assertEqual(result, {})
        self.assertEqual(session.queries, [])

    def test_empty_doc_ids_returns_empty_without_query(self):
        session = FakeSession()
        result = neighbor_documents(session, [], hops=2)
        self.assertEqual(result, {})
        self.assertEqual(session.queries, [])

    def test_returns_doc_id_to_hop_mapping(self):
        session = FakeSession()
        session.neighbor_rows = [{"doc_id": "d2", "hop": 1}, {"doc_id": "d3", "hop": 2}]
        result = neighbor_documents(session, ["d1"], hops=2)
        self.assertEqual(result, {"d2": 1, "d3": 2})
        query, params = session.queries[0]
        self.assertIn("*1..2", query)
        self.assertEqual(params["doc_ids"], ["d1"])


class ChunksForDocumentBySimilarityTests(unittest.TestCase):
    def test_returns_rows_for_doc(self):
        session = FakeSession()
        session.doc_chunk_rows["d2"] = [
            {"chunk_id": "c9", "text": "nội dung", "heading": None, "doc_id": "d2", "level": "doan", "score": 0.5}
        ]
        rows = chunks_for_document_by_similarity(session, "d2", [0.1], k=2)
        self.assertEqual(rows, session.doc_chunk_rows["d2"])


class SearchContextTests(unittest.TestCase):
    def test_hops_zero_only_direct_results(self):
        session = FakeSession()
        session.direct_rows = [
            {"chunk_id": "c1", "text": "a", "heading": "H1", "doc_id": "d1", "level": "dieu", "score": 0.9},
            {"chunk_id": "c2", "text": "b", "heading": "H2", "doc_id": "d1", "level": "dieu", "score": 0.7},
        ]
        result = search_context(session, [0.1], SearchConfig(top_k_direct=2, hops=0))
        self.assertEqual([c.chunk_id for c in result], ["c1", "c2"])
        self.assertTrue(all(c.hop == 0 for c in result))
        # hops=0 không được gọi truy vấn neighbor_documents.
        self.assertFalse(any("UNWIND $doc_ids AS start_id" in q for q, _ in session.queries))

    def test_hops_expands_with_neighbor_chunks(self):
        session = FakeSession()
        session.direct_rows = [
            {"chunk_id": "c1", "text": "a", "heading": "H1", "doc_id": "d1", "level": "dieu", "score": 0.9},
        ]
        session.neighbor_rows = [{"doc_id": "d2", "hop": 1}]
        session.doc_chunk_rows["d2"] = [
            {"chunk_id": "c5", "text": "e", "heading": "H5", "doc_id": "d2", "level": "dieu", "score": 0.3},
        ]
        result = search_context(session, [0.1], SearchConfig(top_k_direct=1, top_k_per_hop=1, hops=1))
        ids = [c.chunk_id for c in result]
        self.assertEqual(ids, ["c1", "c5"])
        self.assertEqual(result[0].hop, 0)
        self.assertEqual(result[1].hop, 1)

    def test_duplicate_chunk_keeps_smaller_hop(self):
        # c1 xuất hiện cả ở kết quả trực tiếp (hop 0) lẫn trong danh sách chunk
        # của một Document lân cận (giả lập trùng) — phải giữ hop=0.
        session = FakeSession()
        session.direct_rows = [
            {"chunk_id": "c1", "text": "a", "heading": "H1", "doc_id": "d1", "level": "dieu", "score": 0.9},
        ]
        session.neighbor_rows = [{"doc_id": "d2", "hop": 1}]
        session.doc_chunk_rows["d2"] = [
            {"chunk_id": "c1", "text": "a", "heading": "H1", "doc_id": "d1", "level": "dieu", "score": 0.1},
        ]
        result = search_context(session, [0.1], SearchConfig(top_k_direct=1, top_k_per_hop=1, hops=1))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].hop, 0)
        self.assertEqual(result[0].score, 0.9)

    def test_sorted_by_hop_then_score_desc(self):
        session = FakeSession()
        session.direct_rows = [
            {"chunk_id": "low", "text": "a", "heading": None, "doc_id": "d1", "level": "doan", "score": 0.2},
            {"chunk_id": "high", "text": "b", "heading": None, "doc_id": "d1", "level": "doan", "score": 0.8},
        ]
        result = search_context(session, [0.1], SearchConfig(top_k_direct=2, hops=0))
        self.assertEqual([c.chunk_id for c in result], ["high", "low"])


if __name__ == "__main__":
    unittest.main()
