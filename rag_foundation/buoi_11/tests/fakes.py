"""FakeSession dùng chung cho toàn bộ test Buổi 11 — ghi lại Cypher đã 'chạy'
để assert, không mở kết nối Neo4j thật (SPEC_buoi_11.md mục 8).

Dispatch theo từ khoá đặc trưng trong câu Cypher (mỗi hàm ở graph_search.py
sinh một dạng câu lệnh khác nhau đủ để phân biệt), trả về dữ liệu giả cấu
hình sẵn qua các thuộc tính public.
"""

from __future__ import annotations


class FakeSession:
    def __init__(self):
        self.queries: list[tuple[str, dict]] = []

        # Cấu hình dữ liệu giả — test chỉnh trực tiếp trước khi gọi hàm.
        self.index_names: list[str] = []
        self.direct_rows: list[dict] = []
        self.neighbor_rows: list[dict] = []
        # doc_id -> list[dict] cho chunks_for_document_by_similarity
        self.doc_chunk_rows: dict[str, list[dict]] = {}

    def run(self, query: str, **params):
        self.queries.append((query, params))

        if "SHOW INDEXES" in query:
            return [{"name": n} for n in self.index_names]

        if "db.index.vector.queryNodes" in query:
            return list(self.direct_rows)

        if "UNWIND $doc_ids AS start_id" in query:
            return list(self.neighbor_rows)

        if "vector.similarity.cosine" in query:
            doc_id = params.get("doc_id")
            return list(self.doc_chunk_rows.get(doc_id, []))

        if "CREATE VECTOR INDEX" in query:
            return []

        return []
