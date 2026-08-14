"""Bước 1–2 (SPEC_buoi_11.md mục 2, 4, 5): kết nối Neo4j `kb-hops`, tìm kiếm
vector và mở rộng đa bước (multi-hop) qua quan hệ liên văn bản.

`driver_factory` và `embed_fn` (ở lớp gọi) luôn injectable — test dùng
FakeSession, không mở kết nối mạng thật, không tải model thật
(tests/test_graph_search.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, Sequence

DOC_RELATIONSHIP_TYPES = ("CAN_CU", "THAY_THE", "HOP_NHAT")

VECTOR_INDEX_NAME = "chunk_embedding_index"

CREATE_VECTOR_INDEX_STATEMENT = (
    f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS "
    "FOR (c:Chunk) ON c.embedding "
    "OPTIONS {indexConfig: {`vector.dimensions`: 384, "
    "`vector.similarity_function`: 'cosine'}}"
)


@dataclass
class Neo4jConfig:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "kb-hops"

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "kb-hops"),
        )


@dataclass
class SearchConfig:
    top_k_direct: int = 5
    top_k_per_hop: int = 2
    hops: int = 0

    @classmethod
    def from_env(cls, hops: int = 0) -> "SearchConfig":
        return cls(
            top_k_direct=int(os.getenv("TOP_K_DIRECT", "5")),
            top_k_per_hop=int(os.getenv("TOP_K_PER_HOP", "2")),
            hops=hops,
        )


@dataclass
class ContextChunk:
    chunk_id: str
    text: str
    heading: str | None
    doc_id: str
    level: str
    score: float
    hop: int

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "heading": self.heading,
            "doc_id": self.doc_id,
            "level": self.level,
            "score": self.score,
            "hop": self.hop,
        }


class SessionLike(Protocol):
    def run(self, query: str, **params): ...


class DriverLike(Protocol):
    def session(self, database: str | None = None) -> SessionLike: ...

    def close(self) -> None: ...


def default_driver_factory(config: Neo4jConfig) -> DriverLike:
    """Lazy import neo4j — chỉ cần khi thực sự kết nối, không bắt buộc lúc test."""

    from neo4j import GraphDatabase  # type: ignore

    return GraphDatabase.driver(config.uri, auth=(config.user, config.password))


def has_vector_index(session: SessionLike) -> bool:
    """Kiểm tra vector index đã tồn tại chưa. KHÔNG tự tạo ngầm nếu thiếu —
    thao tác cấu trúc DB phải tường minh (nhất quán với cách Buổi 10 xử lý
    `CREATE DATABASE`, xem SPEC mục 4)."""

    result = session.run("SHOW INDEXES YIELD name RETURN name")
    names = {row["name"] for row in result}
    return VECTOR_INDEX_NAME in names


def create_vector_index(session: SessionLike) -> None:
    session.run(CREATE_VECTOR_INDEX_STATEMENT)


def vector_search(session: SessionLike, query_vector: Sequence[float], k: int) -> list[dict]:
    """Bước 2b: tìm k chunk gần nhất với query_vector bằng native vector index.

    QUAN TRỌNG: node (:Chunk) KHÔNG có thuộc tính `doc_id` lưu sẵn (đúng schema
    Buổi 10 — chỉ Chunk gốc mới nối [:PART_OF] thẳng tới Document, các Chunk
    con biết văn bản của mình qua chuỗi [:PARENT_OF] lên tới gốc). Phải truy
    ngược lên Chunk gốc (không có ai trỏ PARENT_OF vào) rồi mới lấy doc_id từ
    Document — lấy trực tiếp `node.doc_id` sẽ luôn ra NULL (lỗi đã gặp thật khi
    chạy `compare` lần đầu, xem REVIEW_buoi_11.md)."""

    result = session.run(
        f"CALL db.index.vector.queryNodes('{VECTOR_INDEX_NAME}', $k, $query_vector) "
        "YIELD node, score "
        "MATCH (top:Chunk)-[:PARENT_OF*0..]->(node) "
        "WHERE NOT ()-[:PARENT_OF]->(top) "
        "MATCH (top)-[:PART_OF]->(d:Document) "
        "RETURN node.chunk_id AS chunk_id, node.text AS text, node.heading AS heading, "
        "d.doc_id AS doc_id, node.level AS level, score",
        k=k,
        query_vector=list(query_vector),
    )
    return list(result)


def neighbor_documents(
    session: SessionLike, doc_ids: Sequence[str], hops: int
) -> dict[str, int]:
    """Bước 2c: trả về {doc_id_lân_cận: khoảng_cách_hop_nhỏ_nhất} trong phạm vi
    `hops` bước, duyệt KHÔNG phân biệt chiều qua CAN_CU/THAY_THE/HOP_NHAT
    (SPEC mục 5). Không bao gồm chính các doc_ids gốc.

    `hops` được nội suy thẳng vào chuỗi Cypher (không qua $param) vì Cypher
    không cho tham số hoá cận biến-độ-dài — an toàn vì `hops` luôn là số
    nguyên đến từ argparse (CLI --hops), không phải chuỗi người dùng nhập tay.
    """

    if hops <= 0 or not doc_ids:
        return {}
    query = (
        "UNWIND $doc_ids AS start_id "
        "MATCH (start:Document {doc_id: start_id}) "
        f"MATCH path = (start)-[:CAN_CU|THAY_THE|HOP_NHAT*1..{int(hops)}]-(neighbor:Document) "
        "WHERE NOT neighbor.doc_id IN $doc_ids "
        "RETURN neighbor.doc_id AS doc_id, min(length(path)) AS hop"
    )
    result = session.run(query, doc_ids=list(doc_ids))
    return {row["doc_id"]: row["hop"] for row in result}


def chunks_for_document_by_similarity(
    session: SessionLike, doc_id: str, query_vector: Sequence[float], k: int
) -> list[dict]:
    """Bước 2d: top-k chunk của MỘT Document cụ thể, xếp hạng theo cosine
    similarity với query_vector — dùng cho các Document lân cận tìm được qua
    multi-hop (không cần index riêng, dùng hàm `vector.similarity.cosine` có
    sẵn trong Neo4j 5.x+ để tính điểm ad-hoc trên tập nhỏ)."""

    result = session.run(
        "MATCH (d:Document {doc_id: $doc_id})<-[:PART_OF]-(top:Chunk) "
        "MATCH (top)-[:PARENT_OF*0..]->(c:Chunk) "
        "WHERE c.embedding IS NOT NULL "
        "WITH DISTINCT c, vector.similarity.cosine(c.embedding, $query_vector) AS score "
        "RETURN c.chunk_id AS chunk_id, c.text AS text, c.heading AS heading, "
        "$doc_id AS doc_id, c.level AS level, score "
        "ORDER BY score DESC LIMIT $k",
        doc_id=doc_id,
        query_vector=list(query_vector),
        k=k,
    )
    return list(result)


def search_context(
    session: SessionLike,
    query_vector: Sequence[float],
    config: SearchConfig,
) -> list[ContextChunk]:
    """Bước 2 tổng hợp: vector search trực tiếp (hop=0) + mở rộng multi-hop
    (hop=1..N). Trả về danh sách ContextChunk đã loại trùng theo chunk_id
    (giữ hop nhỏ nhất), sắp theo (hop tăng dần, score giảm dần)."""

    direct = vector_search(session, query_vector, config.top_k_direct)
    by_chunk_id: dict[str, ContextChunk] = {}
    doc_ids_seen: set[str] = set()

    for row in direct:
        doc_ids_seen.add(row["doc_id"])
        by_chunk_id[row["chunk_id"]] = ContextChunk(
            chunk_id=row["chunk_id"],
            text=row["text"],
            heading=row["heading"],
            doc_id=row["doc_id"],
            level=row["level"],
            score=row["score"],
            hop=0,
        )

    if config.hops > 0 and doc_ids_seen:
        neighbors = neighbor_documents(session, sorted(doc_ids_seen), config.hops)
        for doc_id, hop in sorted(neighbors.items()):
            rows = chunks_for_document_by_similarity(
                session, doc_id, query_vector, config.top_k_per_hop
            )
            for row in rows:
                existing = by_chunk_id.get(row["chunk_id"])
                if existing is not None and existing.hop <= hop:
                    continue
                by_chunk_id[row["chunk_id"]] = ContextChunk(
                    chunk_id=row["chunk_id"],
                    text=row["text"],
                    heading=row["heading"],
                    doc_id=row["doc_id"],
                    level=row["level"],
                    score=row["score"],
                    hop=hop,
                )

    return sorted(by_chunk_id.values(), key=lambda c: (c.hop, -c.score))
