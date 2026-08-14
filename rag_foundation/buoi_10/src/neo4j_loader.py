"""Bước 3–5 (SPEC_buoi_10.md mục 2, 5, 6, 8): kết nối và nạp đồ thị Neo4j `kb-hops`.

`driver_factory` luôn injectable — test dùng FakeDriver ghi lại các câu Cypher
đã "chạy" mà không mở kết nối mạng thật (tests/test_neo4j_loader.py). Đây là
lớp duy nhất trong Buổi 10 được phép chạm mạng.

Tất cả câu ghi dùng MERGE trên khoá nghiệp vụ (doc_id / chunk_id) để việc nạp
là idempotent — chạy lại pipeline không tạo node/quan hệ trùng (SPEC mục 5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from .html_parser import Chunk

DOC_RELATIONSHIP_TYPES = ("CAN_CU", "THAY_THE", "HOP_NHAT")


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
class DocumentMeta:
    doc_id: str
    title: str
    doc_type: str | None
    source_file: str
    issue_number: str | None = None
    issue_date: str | None = None
    effective_date: str | None = None


@dataclass
class DocRelationship:
    from_doc_id: str
    rel_type: str  # phải thuộc DOC_RELATIONSHIP_TYPES
    to_doc_id: str


class SessionLike(Protocol):
    def run(self, query: str, **params): ...


class DriverLike(Protocol):
    def session(self, database: str | None = None) -> SessionLike: ...

    def close(self) -> None: ...


def default_driver_factory(config: Neo4jConfig) -> DriverLike:
    """Lazy import neo4j — chỉ cần khi thực sự kết nối, không bắt buộc lúc test."""

    from neo4j import GraphDatabase  # type: ignore

    return GraphDatabase.driver(config.uri, auth=(config.user, config.password))


CONSTRAINT_STATEMENTS = (
    "CREATE CONSTRAINT document_doc_id IF NOT EXISTS "
    "FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_chunk_id IF NOT EXISTS "
    "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
)


def ensure_constraints(session: SessionLike) -> None:
    for stmt in CONSTRAINT_STATEMENTS:
        session.run(stmt)


def upsert_document(session: SessionLike, doc: DocumentMeta) -> None:
    session.run(
        """
        MERGE (d:Document {doc_id: $doc_id})
        SET d.title = $title,
            d.doc_type = $doc_type,
            d.source_file = $source_file,
            d.issue_number = $issue_number,
            d.issue_date = $issue_date,
            d.effective_date = $effective_date,
            d.ingested_at = datetime()
        """,
        doc_id=doc.doc_id,
        title=doc.title,
        doc_type=doc.doc_type,
        source_file=doc.source_file,
        issue_number=doc.issue_number,
        issue_date=doc.issue_date,
        effective_date=doc.effective_date,
    )


def upsert_chunk(
    session: SessionLike, chunk: Chunk, embedding: list[float], embedding_model: str
) -> None:
    session.run(
        """
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.level = $level,
            c.heading = $heading,
            c.text = $text,
            c.order_index = $order_index,
            c.embedding = $embedding,
            c.embedding_model = $embedding_model,
            c.embedding_dim = $embedding_dim
        """,
        chunk_id=chunk.chunk_id,
        level=chunk.level,
        heading=chunk.heading,
        text=chunk.text,
        order_index=chunk.order_index,
        embedding=embedding,
        embedding_model=embedding_model,
        embedding_dim=len(embedding),
    )


def link_chunk_to_document(session: SessionLike, chunk_id: str, doc_id: str) -> None:
    """(:Chunk)-[:PART_OF]->(:Document) — mọi chunk gốc phải nối thẳng theo tiêu đề
    tương ứng, đúng yêu cầu đề bài Bước 4, không chỉ suy ra qua chuỗi PARENT_OF."""

    session.run(
        """
        MATCH (c:Chunk {chunk_id: $chunk_id})
        MATCH (d:Document {doc_id: $doc_id})
        MERGE (c)-[:PART_OF]->(d)
        """,
        chunk_id=chunk_id,
        doc_id=doc_id,
    )


def link_parent_child(session: SessionLike, parent_id: str, child_id: str) -> None:
    session.run(
        """
        MATCH (p:Chunk {chunk_id: $parent_id})
        MATCH (c:Chunk {chunk_id: $child_id})
        MERGE (p)-[:PARENT_OF]->(c)
        """,
        parent_id=parent_id,
        child_id=child_id,
    )


def link_next(session: SessionLike, from_id: str, to_id: str) -> None:
    session.run(
        """
        MATCH (a:Chunk {chunk_id: $from_id})
        MATCH (b:Chunk {chunk_id: $to_id})
        MERGE (a)-[:NEXT]->(b)
        """,
        from_id=from_id,
        to_id=to_id,
    )


def link_documents(session: SessionLike, rel: DocRelationship) -> None:
    if rel.rel_type not in DOC_RELATIONSHIP_TYPES:
        raise ValueError(
            f"rel_type không hợp lệ: {rel.rel_type!r}, phải thuộc {DOC_RELATIONSHIP_TYPES}"
        )
    session.run(
        f"""
        MATCH (a:Document {{doc_id: $from_id}})
        MATCH (b:Document {{doc_id: $to_id}})
        MERGE (a)-[:{rel.rel_type}]->(b)
        """,
        from_id=rel.from_doc_id,
        to_id=rel.to_doc_id,
    )


def load_document_relationships(
    session: SessionLike, relationships: list[DocRelationship]
) -> None:
    """Nạp toàn bộ quan hệ cấp tài liệu. Validate rel_type trước khi chạy Cypher
    để một dòng khai báo sai không kịp ghi gì vào đồ thị."""

    for rel in relationships:
        if rel.rel_type not in DOC_RELATIONSHIP_TYPES:
            raise ValueError(
                f"rel_type không hợp lệ: {rel.rel_type!r} "
                f"({rel.from_doc_id} -> {rel.to_doc_id}), phải thuộc {DOC_RELATIONSHIP_TYPES}"
            )
    for rel in relationships:
        link_documents(session, rel)


def compute_next_links(chunks: list[Chunk]) -> list[tuple[str, str]]:
    """Suy ra cặp (from_id, to_id) cho quan hệ NEXT: chỉ giữa anh em liền kề
    CÙNG cha, sắp theo order_index — theo đúng ràng buộc SPEC mục 5."""

    by_parent: dict[str | None, list[Chunk]] = {}
    for c in chunks:
        by_parent.setdefault(c.parent_id, []).append(c)

    pairs: list[tuple[str, str]] = []
    for siblings in by_parent.values():
        siblings_sorted = sorted(siblings, key=lambda c: c.order_index)
        for a, b in zip(siblings_sorted, siblings_sorted[1:]):
            pairs.append((a.chunk_id, b.chunk_id))
    return pairs


def load_document_chunks(
    session: SessionLike,
    doc: DocumentMeta,
    chunks: list[Chunk],
    embeddings: dict[str, list[float]],
    embedding_model: str,
) -> None:
    """Nạp toàn bộ một văn bản: Document + tất cả Chunk + PART_OF + PARENT_OF + NEXT."""

    upsert_document(session, doc)
    for chunk in chunks:
        embedding = embeddings.get(chunk.chunk_id)
        if embedding is None:
            raise ValueError(f"Thiếu embedding cho chunk_id={chunk.chunk_id}")
        upsert_chunk(session, chunk, embedding, embedding_model)

    # Chunk cấp cao nhất (không có parent_id) nối PART_OF thẳng tới Document.
    for chunk in chunks:
        if chunk.parent_id is None:
            link_chunk_to_document(session, chunk.chunk_id, doc.doc_id)
        else:
            link_parent_child(session, chunk.parent_id, chunk.chunk_id)

    for from_id, to_id in compute_next_links(chunks):
        link_next(session, from_id, to_id)


VERIFY_QUERIES: dict[str, str] = {
    "document_count": "MATCH (d:Document) RETURN count(d) AS n",
    "document_relationship_count": (
        "MATCH (:Document)-[r:CAN_CU|THAY_THE|HOP_NHAT]->(:Document) RETURN count(r) AS n"
    ),
    "chunk_count": "MATCH (c:Chunk) RETURN count(c) AS n",
    # Chunk mồ côi: không nối được về Document và cũng không có cha nào.
    "orphan_chunks": (
        "MATCH (c:Chunk) "
        "WHERE NOT (c)-[:PART_OF]->(:Document) AND NOT ()-[:PARENT_OF]->(c) "
        "RETURN count(c) AS n"
    ),
    # NEXT sai: nối hai chunk KHÁC cha. Theo SPEC mục 5, NEXT chỉ được nối giữa
    # anh em cùng cha, nên con số này phải bằng 0.
    "next_cross_parent": (
        "MATCH (a:Chunk)-[:NEXT]->(b:Chunk) "
        "WHERE NOT ( (a)<-[:PARENT_OF]-()-[:PARENT_OF]->(b) ) "
        "AND NOT ( NOT ()-[:PARENT_OF]->(a) AND NOT ()-[:PARENT_OF]->(b) ) "
        "RETURN count(*) AS n"
    ),
    # Chunk có nhiều hơn một cha — vi phạm invariant "mỗi chunk đúng một parent".
    "multi_parent_chunks": (
        "MATCH (c:Chunk)<-[:PARENT_OF]-(p) "
        "WITH c, count(p) AS parents WHERE parents > 1 "
        "RETURN count(c) AS n"
    ),
    # Chunk chưa có vector nhúng — nếu > 0 thì tìm kiếm ngữ nghĩa sẽ bỏ sót.
    "chunks_without_embedding": (
        "MATCH (c:Chunk) WHERE c.embedding IS NULL RETURN count(c) AS n"
    ),
}


def verify_load(session: SessionLike) -> dict:
    """Bước 5: đếm số liệu để đối chiếu với tiêu chí nghiệm thu (SPEC mục 8).

    Chỉ ĐỌC, không ghi. Mọi chỉ tiêu toàn vẹn (`orphan_chunks`,
    `next_cross_parent`, `multi_parent_chunks`, `chunks_without_embedding`)
    đều phải bằng 0.
    """

    return {key: session.run(query).single()["n"] for key, query in VERIFY_QUERIES.items()}


#: Các chỉ tiêu bắt buộc bằng 0 — dùng cho báo cáo ở pipeline.
INTEGRITY_KEYS = (
    "orphan_chunks",
    "next_cross_parent",
    "multi_parent_chunks",
    "chunks_without_embedding",
)
