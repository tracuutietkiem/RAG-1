"""
BUOI 15 - PROMPT 3: Secure Retrieval Pipeline.

    secure_search(question, user_roles, method="hybrid_rerank", top_k=None, candidate_k=None)

method: bm25 | dense | hybrid | hybrid_rerank
user_roles: list vai tro cua nguoi dung hien tai, vi du ["Guest"] hoac ["HR", "Staff"].

NGUYEN TAC BAT BUOC: loc quyen truoc khi tinh diem/xep hang o CA 3 tang:

  - BM25   : loc DataFrame (chunks_secure.csv) TRUOC khi build BM25 index
             (pre-filtering dung nghia den).
  - Dense  : hau loc (post-filtering) tren ket qua cosine similarity da tinh
             tren toan corpus (tai su dung embedding cache co san cua Buoi 14) -
             de bai cho phep ca pre-filter va post-filter cho Dense.
  - Graph  : mệnh đề Cypher `WHERE any(role IN ... WHERE role IN $user_roles)`.

Hybrid Fusion (RRF) va Reranker CHI lam viec tren candidate DA duoc loc quyen o
tang BM25/Dense - khong bao gio co tai lieu cam lot vao Reranker (xem
secure_rerank_search: co kiem tra "defense-in-depth" truoc khi goi Reranker).

Ket qua tra ve cung cau truc voi pipeline.retrieve() cua Buoi 14 (rank, chunk_id,
document_id, text, score, citation, retrieval_method), CONG THEM truong
`allowed_roles` cua tung tai lieu de doi sanh/hien thi tren UI.
"""

from __future__ import annotations

import csv
import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import dense_retriever  # noqa: E402
from src import reranker as reranker_mod  # noqa: E402
from src.bm25_retriever import tokenize  # noqa: E402
from src.citation import attach  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

METHODS = ("bm25", "dense", "hybrid", "hybrid_rerank")


# ============================================================== corpus an toan
def _parse_roles(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return [x.strip() for x in raw.split(",") if x.strip()]


@lru_cache(maxsize=1)
def load_secure_records() -> tuple[dict, ...]:
    """Doc chunks_secure.csv (ket qua cua scripts/assign_security_tags.py)."""
    path = config.CHUNKS_SECURE_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"Chua co {path}. Chay truoc: python scripts/assign_security_tags.py"
        )
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise RuntimeError(f"{path} rong.")
    out = []
    for r in rows:
        rec = dict(r)
        rec["allowed_roles"] = _parse_roles(r.get("allowed_roles", ""))
        out.append(rec)
    return tuple(out)


@lru_cache(maxsize=1)
def secure_chunk_index() -> dict:
    return {r["chunk_id"]: r for r in load_secure_records()}


@lru_cache(maxsize=1)
def _chunk_role_lookup() -> dict:
    return {r["chunk_id"]: r["allowed_roles"] for r in load_secure_records()}


@lru_cache(maxsize=1)
def _secure_df() -> "pd.DataFrame":
    """DataFrame Pandas cho toan bo corpus bao mat - dung de loc TRUOC BM25,
    dung y yeu cau de bai 'Lọc trực tiếp trên Pandas DataFrame'."""
    df = pd.DataFrame(list(load_secure_records()))
    df["_role_set"] = df["allowed_roles"].apply(lambda rs: frozenset(rs))
    return df


def _filter_df_by_roles(df: "pd.DataFrame", user_roles) -> "pd.DataFrame":
    role_set = frozenset(user_roles)
    mask = df["_role_set"].apply(lambda rs: bool(rs & role_set))
    return df[mask]


def filter_records_by_roles(records, user_roles) -> list[dict]:
    """Ham loc dung chung: giu lai record neu GIAO giua allowed_roles cua record
    va user_roles KHAC RONG (chi can 1 vai tro trung la du quyen xem)."""
    role_set = frozenset(user_roles)
    return [r for r in records if role_set & frozenset(r.get("allowed_roles") or [])]


def visibility_stats(user_roles) -> dict:
    """So chunk nguoi dung voi user_roles nay duoc thay / bi loc bo - dung de
    hien thi thong bao 'Đã lọc bỏ X kết quả do không đủ quyền truy cập' o UI."""
    total = len(load_secure_records())
    visible = len(_filter_df_by_roles(_secure_df(), user_roles))
    return {"total_chunks": total, "visible_chunks": visible,
            "hidden_chunks": total - visible}


# ==================================================================== BM25
@lru_cache(maxsize=64)
def _bm25_index_for_roles(roles_key: frozenset):
    """Build BM25 index CHI tren cac dong DataFrame da qua loc quyen (pre-filter).
    Cache theo tap vai tro de khong build lai moi lan nguoi dung go cau hoi moi
    (Streamlit rerun lien tuc), nhung van build lai khi doi to hop vai tro."""
    from rank_bm25 import BM25Okapi

    df = _secure_df()
    filtered = _filter_df_by_roles(df, roles_key)
    records = filtered.drop(columns=["_role_set"]).to_dict("records")
    if not records:
        return records, None
    corpus_tokens = [tokenize(r.get("index_text") or r.get("text", "")) for r in records]
    return records, BM25Okapi(corpus_tokens)


def secure_bm25_search(question: str, user_roles, top_k: int = 5) -> list[dict]:
    roles = config.validate_roles(user_roles)
    if not roles:
        return []
    records, bm25 = _bm25_index_for_roles(frozenset(roles))
    if not records or bm25 is None:
        return []
    q_tokens = tokenize(question)
    if not q_tokens:
        return []
    scores = bm25.get_scores(q_tokens)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    results = []
    for rank, idx in enumerate(order[:top_k], start=1):
        if scores[idx] <= 0:
            continue
        rec = records[idx]
        results.append(
            attach(
                rec,
                rank=rank,
                retrieval_score=round(float(scores[idx]), 6),
                retrieval_method="secure_bm25",
                allowed_roles=rec["allowed_roles"],
            )
        )
    return results


# ==================================================================== Dense
def secure_dense_search(question: str, user_roles, top_k: int = 5) -> list[dict]:
    """Hau loc (post-filtering): tai su dung embedding matrix da tinh san cua
    Buoi 14 (toan bo corpus), sap xep giam dan theo cosine, roi BO QUA moi ung
    vien khong co giao voi user_roles cho DEN KHI du top_k ket qua HOP LE. Dung
    duyet tuan tu tren toan corpus (2.528 dong) nen khong the "ro ri" ket qua bi
    cam ra ngoai boi vi vong lap chi append khi da qua kiem tra quyen."""
    roles = config.validate_roles(user_roles)
    if not roles:
        return []
    role_set = frozenset(roles)
    dr = dense_retriever.get_retriever()
    q = dr.backend.encode_query(question)
    scores = dr.matrix @ q
    order = np.argsort(-scores)
    lookup = _chunk_role_lookup()

    results = []
    rank = 0
    for idx in order:
        rec = dr.records[int(idx)]
        allowed = lookup.get(rec["chunk_id"])
        if allowed is None:
            # Chunk khong co trong chunks_secure.csv (vi du corpus bi doi sau khi
            # gan tag) -> FAIL-CLOSED: coi nhu KHONG co quyen, khong tra ve.
            continue
        if not (role_set & frozenset(allowed)):
            continue
        rank += 1
        results.append(
            attach(
                rec,
                rank=rank,
                retrieval_score=round(float(scores[int(idx)]), 6),
                retrieval_method="secure_dense",
                allowed_roles=allowed,
            )
        )
        if rank >= top_k:
            break
    return results


# ==================================================================== Hybrid RRF
def secure_hybrid_search(
    question: str, user_roles, top_k: int | None = None, candidate_k: int | None = None
) -> list[dict]:
    top_k = top_k or config.FINAL_TOP_K
    candidate_k = candidate_k or config.CANDIDATE_K

    bm_hits = secure_bm25_search(question, user_roles, candidate_k)
    dn_hits = secure_dense_search(question, user_roles, candidate_k)

    bm_rank = {h["chunk_id"]: h["rank"] for h in bm_hits}
    dn_rank = {h["chunk_id"]: h["rank"] for h in dn_hits}
    bm_score = {h["chunk_id"]: h["retrieval_score"] for h in bm_hits}
    dn_score = {h["chunk_id"]: h["retrieval_score"] for h in dn_hits}
    roles_by_chunk = {h["chunk_id"]: h["allowed_roles"] for h in (*bm_hits, *dn_hits)}

    fused: dict[str, float] = {}
    for cid, rank in bm_rank.items():
        fused[cid] = fused.get(cid, 0.0) + config.RRF_BM25_WEIGHT / (config.RRF_K + rank)
    for cid, rank in dn_rank.items():
        fused[cid] = fused.get(cid, 0.0) + config.RRF_DENSE_WEIGHT / (config.RRF_K + rank)

    ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
    index = secure_chunk_index()

    results = []
    for final_rank, (cid, score) in enumerate(ordered[:top_k], start=1):
        rec = index.get(cid)
        if rec is None:
            continue
        results.append(
            attach(
                rec,
                final_rank=final_rank,
                rank=final_rank,
                bm25_rank=bm_rank.get(cid),
                dense_rank=dn_rank.get(cid),
                bm25_score=bm_score.get(cid),
                dense_score=dn_score.get(cid),
                rrf_score=round(score, 8),
                retrieval_score=round(score, 8),
                retrieval_method="secure_hybrid",
                allowed_roles=roles_by_chunk.get(cid, rec.get("allowed_roles")),
            )
        )
    return results


def secure_hybrid_candidates(question: str, user_roles, candidate_k: int | None = None) -> list[dict]:
    candidate_k = candidate_k or config.CANDIDATE_K
    return secure_hybrid_search(question, user_roles, top_k=candidate_k, candidate_k=candidate_k)


# ==================================================================== Rerank
def secure_rerank_search(
    question: str, user_roles, top_k: int | None = None, candidate_k: int | None = None
) -> list[dict]:
    top_k = top_k or config.FINAL_TOP_K
    candidate_k = candidate_k or config.CANDIDATE_K
    candidates = secure_hybrid_candidates(question, user_roles, candidate_k=candidate_k)

    # Defense-in-depth: KHONG BAO GIO tin tuong mu quang buoc loc truoc. Loc lai
    # lan nua ngay truoc cua Reranker - day chinh la cau tra loi cho cau hoi
    # thao luan #3 (tai sao phai loc TRUOC Reranker chu khong phai SAU): neu loc
    # sau, Reranker da lang phi tai nguyen cham diem tai lieu cam VA co the day
    # tai lieu cam len #1 roi bi xoa, lam Top-k con lai thieu hut ket qua hop le.
    role_set = frozenset(config.validate_roles(user_roles))
    safe_candidates = [
        c for c in candidates if role_set & frozenset(c.get("allowed_roles") or [])
    ]

    reranked = reranker_mod.get_reranker().rerank(question, safe_candidates, top_k=top_k)
    for r in reranked:
        r["retrieval_method"] = "secure_hybrid_rerank"
    return reranked


# ==================================================================== dispatcher
def secure_search(
    question: str,
    user_roles,
    method: str = "hybrid_rerank",
    top_k: int | None = None,
    candidate_k: int | None = None,
) -> dict:
    method = (method or "hybrid_rerank").strip().lower()
    if method not in METHODS:
        raise ValueError(f"method phai thuoc {METHODS}, nhan duoc {method!r}")
    roles = config.validate_roles(user_roles)
    if not roles:
        raise ValueError("user_roles khong duoc rong - phai truyen it nhat 1 vai tro hop le.")
    top_k = top_k or config.FINAL_TOP_K
    candidate_k = candidate_k or config.CANDIDATE_K

    out: dict = {
        "method": method, "user_roles": roles, "results": [], "before_rerank": [],
    }

    if method == "bm25":
        out["results"] = secure_bm25_search(question, roles, top_k)
    elif method == "dense":
        out["results"] = secure_dense_search(question, roles, top_k)
    elif method == "hybrid":
        out["results"] = secure_hybrid_search(question, roles, top_k=top_k, candidate_k=candidate_k)
    else:  # hybrid_rerank
        out["before_rerank"] = secure_hybrid_candidates(question, roles, candidate_k=candidate_k)
        out["results"] = secure_rerank_search(question, roles, top_k=top_k, candidate_k=candidate_k)

    for r in out["results"]:
        r.setdefault("score", r.get("retrieval_score"))

    stats = visibility_stats(roles)
    out.update({
        "n_total_chunks": stats["total_chunks"],
        "n_visible_chunks": stats["visible_chunks"],
        "n_hidden_chunks": stats["hidden_chunks"],
    })
    return out


# ==================================================================== Graph (Neo4j)
def neo4j_status() -> tuple[bool, str]:
    from src import graph_hints
    return graph_hints.neo4j_status()


def secure_graph_query(document_ids: list[str], user_roles) -> list[dict]:
    """Truy van Cypher THAM CHIEU TRUC TIEP theo yeu cau PROMPT 3, muc 3:

        MATCH (v:VanBan)-[:CONTAINS]->(d:DieuKhoan)
        WHERE any(role IN d.allowed_roles WHERE role IN $user_roles)
        RETURN v, d

    Bo sung xu ly cho cau hoi thao luan #1: neu (:DieuKhoan) KHONG co
    allowed_roles rieng, ke thua allowed_roles cua (:VanBan) cha bang
    `coalesce(d.allowed_roles, v.allowed_roles, [])`. Neu CA HAI deu thieu,
    coalesce tra ve [] -> `any(...)` luon False -> AN TOAN TOI DA (fail-closed,
    thay vi fail-open neu lo mac dinh cho qua khi thieu du lieu)."""
    ok, msg = neo4j_status()
    if not ok or not document_ids:
        return []
    roles = config.validate_roles(user_roles)
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        with driver.session(database=config.NEO4J_DATABASE) as s:
            rows = s.run(
                """
                MATCH (v:VanBan)-[:CONTAINS]->(d:DieuKhoan)
                WHERE v.id IN $doc_ids
                  AND any(role IN coalesce(d.allowed_roles, v.allowed_roles, [])
                          WHERE role IN $user_roles)
                RETURN v.so_ky_hieu AS so_ky_hieu, d.id AS chunk_id,
                       coalesce(d.allowed_roles, v.allowed_roles, []) AS allowed_roles
                LIMIT 200
                """,
                doc_ids=document_ids, user_roles=roles,
            )
            return [dict(rec) for rec in rows]
    finally:
        driver.close()


def secure_graph_hints(results: list[dict], user_roles, limit_docs: int = 5) -> dict:
    """Nhu src/graph_hints.graph_hints() cua Buoi 14, nhung LOC THEO QUYEN: chi
    tra ve quan he cua VanBan ma nguoi dung co it nhat mot Dieu duoc phep xem."""
    docs: dict[str, list[str]] = {}
    for r in results:
        sk = r.get("so_ky_hieu") or r.get("document_id", "")
        docs.setdefault(sk, []).append(r.get("chunk_id", ""))
    docs = dict(list(docs.items())[:limit_docs])

    ok, msg = neo4j_status()
    if not ok:
        return {
            "available": False, "message": msg,
            "documents": [{"so_ky_hieu": sk, "chunk_ids": cids, "relations": []}
                          for sk, cids in docs.items()],
        }

    roles = config.validate_roles(user_roles)
    from neo4j import GraphDatabase

    out = []
    try:
        driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        driver.verify_connectivity()
        with driver.session(database=config.NEO4J_DATABASE) as s:
            for sk, cids in docs.items():
                rows = s.run(
                    """
                    MATCH (v:VanBan {id: $sk})-[r]->(o)
                    WHERE any(role IN coalesce(v.allowed_roles, []) WHERE role IN $user_roles)
                    RETURN type(r) AS type,
                           coalesce(o.so_ky_hieu, o.name, o.id) AS target,
                           r.confidence AS confidence
                    LIMIT 25
                    """,
                    sk=sk, user_roles=roles,
                )
                rels = [
                    {"type": rec["type"], "target": rec["target"], "confidence": rec["confidence"]}
                    for rec in rows if rec["type"] not in ("CONTAINS",)
                ]
                out.append({"so_ky_hieu": sk, "chunk_ids": cids, "relations": rels})
        driver.close()
        return {"available": True, "message": "Neo4j san sang (da loc theo quyen)", "documents": out}
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "message": f"Neo4j khong ket noi duoc: {type(exc).__name__}: {str(exc)[:160]}",
            "documents": [{"so_ky_hieu": sk, "chunk_ids": cids, "relations": []}
                          for sk, cids in docs.items()],
        }
