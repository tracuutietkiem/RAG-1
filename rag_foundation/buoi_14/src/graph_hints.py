"""
GRAPH HINTS - goi y quan he truc tiep tu Mini Knowledge Graph.

Muc tieu cua Buoi 14 la chuan bi du lieu sach cho buoi Graph RAG sau, nen o day
CHI lay quan he TRUC TIEP (1 hop) cua van ban chua chunk duoc retrieve.
Khong traversal nhieu hop, khong bien bai nay thanh Graph RAG.

Neu Neo4j chua san sang: tra ve trang thai ro rang, KHONG lam hong retrieval.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def neo4j_status() -> tuple[bool, str]:
    missing = [k for k, v in {
        "NEO4J_URI": config.NEO4J_URI,
        "NEO4J_USER": config.NEO4J_USER,
        "NEO4J_PASSWORD": config.NEO4J_PASSWORD,
    }.items() if not v]
    if missing:
        return False, f"Neo4j chua san sang: thieu {missing} trong .env"
    try:
        import neo4j  # noqa: F401
    except ImportError:
        return False, "Neo4j chua san sang: chua cai driver (pip install neo4j)"
    return True, "Neo4j san sang"


def graph_hints(results: list[dict], limit_docs: int = 5) -> dict:
    """
    Tra ve:
        available : Neo4j co dung duoc khong
        message   : giai thich khi khong dung duoc
        documents : [{so_ky_hieu, chunk_ids, relations: [{type, target, confidence}]}]
    """
    docs: dict[str, list[str]] = {}
    for r in results:
        sk = r.get("so_ky_hieu") or r.get("document_id", "")
        docs.setdefault(sk, []).append(r.get("chunk_id", ""))
    docs = dict(list(docs.items())[:limit_docs])

    ok, msg = neo4j_status()
    if not ok:
        return {
            "available": False,
            "message": msg,
            "documents": [
                {"so_ky_hieu": sk, "chunk_ids": cids, "relations": []}
                for sk, cids in docs.items()
            ],
        }

    from neo4j import GraphDatabase

    out = []
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        with driver.session(database=config.NEO4J_DATABASE) as s:
            for sk, cids in docs.items():
                rows = s.run(
                    "MATCH (v:VanBan {id: $sk, lab_session: $lab})-[r]->(o) "
                    "RETURN type(r) AS type, "
                    "       coalesce(o.so_ky_hieu, o.name, o.id) AS target, "
                    "       r.confidence AS confidence "
                    "LIMIT 25",
                    sk=sk, lab=config.LAB_SESSION,
                )
                rels = [
                    {"type": rec["type"], "target": rec["target"],
                     "confidence": rec["confidence"]}
                    for rec in rows
                    if rec["type"] not in ("CONTAINS",)
                ]
                out.append({"so_ky_hieu": sk, "chunk_ids": cids, "relations": rels})
        driver.close()
        return {"available": True, "message": "Neo4j san sang", "documents": out}
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "message": f"Neo4j khong ket noi duoc: {type(exc).__name__}: {str(exc)[:160]}",
            "documents": [
                {"so_ky_hieu": sk, "chunk_ids": cids, "relations": []}
                for sk, cids in docs.items()
            ],
        }
