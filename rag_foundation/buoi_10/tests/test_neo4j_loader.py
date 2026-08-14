import unittest

from src.html_parser import parse_html_document
from src.neo4j_loader import (
    INTEGRITY_KEYS,
    VERIFY_QUERIES,
    DocRelationship,
    DocumentMeta,
    compute_next_links,
    ensure_constraints,
    link_documents,
    load_document_chunks,
    verify_load,
)


class FakeResult:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class FakeSession:
    """Ghi lại mọi câu Cypher đã 'chạy' để assert trong test, không mở kết nối
    mạng thật — đúng yêu cầu testability ở SPEC_buoi_10.md mục 7.

    Với các truy vấn của `verify_load`, trả số đếm giả lấy từ `_fake_counts`.
    Việc tra cứu dựa trên VERIFY_QUERIES nên khi thêm chỉ tiêu mới vào loader
    thì test tự động theo kịp, không bị khớp nhầm bằng chuỗi con.
    """

    def __init__(self):
        self.queries: list[tuple[str, dict]] = []
        self._fake_counts = {key: 0 for key in VERIFY_QUERIES}
        self._query_to_key = {q: k for k, q in VERIFY_QUERIES.items()}

    def run(self, query: str, **params):
        self.queries.append((query, params))
        key = self._query_to_key.get(query)
        if key is not None:
            return FakeResult({"n": self._fake_counts[key]})
        return FakeResult({"n": 0})


class ComputeNextLinksTests(unittest.TestCase):
    def test_links_only_siblings_with_same_parent(self):
        html = """
        <html><body>
        <h1>Chương I A</h1>
        <h2>Điều 1. X</h2>
        <p>đoạn a</p>
        <p>đoạn b</p>
        <h2>Điều 2. Y</h2>
        <p>đoạn c</p>
        </body></html>
        """
        chunks = parse_html_document("doc1", html)
        pairs = compute_next_links(chunks)
        # đoạn a -> đoạn b phải nằm trong pairs (cùng cha Điều 1)
        doan_a = next(c for c in chunks if c.text == "đoạn a")
        doan_b = next(c for c in chunks if c.text == "đoạn b")
        self.assertIn((doan_a.chunk_id, doan_b.chunk_id), pairs)
        # đoạn b -> đoạn c KHÔNG được nối vì khác cha (Điều 1 vs Điều 2)
        doan_c = next(c for c in chunks if c.text == "đoạn c")
        self.assertNotIn((doan_b.chunk_id, doan_c.chunk_id), pairs)


class EnsureConstraintsTests(unittest.TestCase):
    def test_runs_two_constraint_statements(self):
        session = FakeSession()
        ensure_constraints(session)
        self.assertEqual(len(session.queries), 2)
        self.assertTrue(all("CONSTRAINT" in q for q, _ in session.queries))


class LinkDocumentsTests(unittest.TestCase):
    def test_rejects_invalid_relationship_type(self):
        session = FakeSession()
        with self.assertRaises(ValueError):
            link_documents(session, DocRelationship("d1", "INVALID_REL", "d2"))

    def test_accepts_valid_relationship_type(self):
        session = FakeSession()
        link_documents(session, DocRelationship("d1", "CAN_CU", "d2"))
        self.assertEqual(len(session.queries), 1)
        self.assertIn("CAN_CU", session.queries[0][0])


class LoadDocumentChunksTests(unittest.TestCase):
    def test_loads_document_and_all_chunks(self):
        html = """
        <html><body>
        <h1>Chương I A</h1>
        <h2>Điều 1. X</h2>
        <p>đoạn a</p>
        </body></html>
        """
        chunks = parse_html_document("doc1", html)
        embeddings = {c.chunk_id: [0.1, 0.2] for c in chunks}
        session = FakeSession()
        doc = DocumentMeta(doc_id="doc1", title="Test", doc_type=None, source_file="doc1.html")

        load_document_chunks(session, doc, chunks, embeddings, "fake-model")

        # 1 MERGE Document + N MERGE Chunk + (N-1 hoặc N quan hệ cấu trúc) + NEXT
        merge_document = [q for q, _ in session.queries if "MERGE (d:Document" in q]
        merge_chunk = [q for q, _ in session.queries if "MERGE (c:Chunk {chunk_id" in q]
        self.assertEqual(len(merge_document), 1)
        self.assertEqual(len(merge_chunk), len(chunks))

    def test_raises_if_embedding_missing(self):
        html = "<html><body><h1>Chương I A</h1><p>đoạn a</p></body></html>"
        chunks = parse_html_document("doc1", html)
        session = FakeSession()
        doc = DocumentMeta(doc_id="doc1", title="T", doc_type=None, source_file="f.html")
        with self.assertRaises(ValueError):
            load_document_chunks(session, doc, chunks, {}, "fake-model")


class VerifyLoadTests(unittest.TestCase):
    def test_returns_all_declared_metrics(self):
        session = FakeSession()
        session._fake_counts.update(
            {"document_count": 15, "document_relationship_count": 8, "chunk_count": 400}
        )
        result = verify_load(session)
        self.assertEqual(set(result), set(VERIFY_QUERIES))
        self.assertEqual(result["document_count"], 15)
        self.assertEqual(result["document_relationship_count"], 8)
        self.assertEqual(result["chunk_count"], 400)

    def test_integrity_keys_are_all_queried(self):
        # Mọi chỉ tiêu toàn vẹn phải có truy vấn tương ứng, tránh trường hợp
        # SPEC khai báo một chỉ tiêu mà code không hề kiểm tra.
        for key in INTEGRITY_KEYS:
            self.assertIn(key, VERIFY_QUERIES)

    def test_integrity_defaults_to_zero(self):
        result = verify_load(FakeSession())
        for key in INTEGRITY_KEYS:
            self.assertEqual(result[key], 0)

    def test_nonzero_integrity_metric_is_reported(self):
        session = FakeSession()
        session._fake_counts["next_cross_parent"] = 3
        session._fake_counts["multi_parent_chunks"] = 1
        result = verify_load(session)
        self.assertEqual(result["next_cross_parent"], 3)
        self.assertEqual(result["multi_parent_chunks"], 1)

    def test_verify_load_is_read_only(self):
        session = FakeSession()
        verify_load(session)
        for query, _ in session.queries:
            upper = query.upper()
            for forbidden in ("MERGE", "CREATE", "DELETE", "SET ", "REMOVE"):
                self.assertNotIn(forbidden, upper, f"verify_load không được ghi: {query}")


if __name__ == "__main__":
    unittest.main()
