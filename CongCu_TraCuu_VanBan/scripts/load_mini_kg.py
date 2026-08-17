#!/usr/bin/env python3
"""
PROMPT 6 - Xay Mini Knowledge Graph va nap vao Neo4j.

Nguon:
    KB_DIR/metadata.csv                        -> node VanBan
    KB_DIR/relationships.csv                   -> quan he THAT
    data/processed/chunks_normalized.csv       -> node DieuKhoan

Ontology MVP:
    (:VanBan)-[:CONTAINS]->(:DieuKhoan)
    (:DieuKhoan)-[:NEXT]->(:DieuKhoan)          (thu tu trong cung van ban)
    (:VanBan)-[:THAM_CHIEU|SUA_DOI_BO_SUNG|THAY_THE_BOI]->(:VanBan)

Cac relationship_type con lai trong relationships.csv (KY_BOI, BAN_HANH_BOI,
THUOC_LINH_VUC, AP_DUNG_CHO) co target KHONG phai van ban ma la thuc the khac.
Mac dinh KHONG nap (giu ontology MVP dung de bai). Bat bang --with-entities
neu muon nap them, khi do moi tao node NguoiKy/CoQuan/LinhVuc/DoiTuongApDung.

AN TOAN:
    - MERGE theo id  -> chay lai khong tao duplicate.
    - Parameterized Cypher.
    - Khong hard-code password; doc tu .env.
    - Moi node/quan he deu co lab_session = "buoi_14".
    - KHONG BAO GIO chay MATCH (n) DETACH DELETE n.
      --clean chi xoa node co lab_session = "buoi_14" va phai kem --yes.

Output: buoi_14/outputs/kg_build_report.md
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# Quan he van ban -> van ban (target la so_ky_hieu)
DOC_TO_DOC = {"THAM_CHIEU", "SUA_DOI_BO_SUNG", "THAY_THE_BOI"}
# Quan he van ban -> thuc the khac (chi nap khi --with-entities)
ENTITY_MAP = {
    "KY_BOI": "NguoiKy",
    "BAN_HANH_BOI": "CoQuan",
    "THUOC_LINH_VUC": "LinhVuc",
    "AP_DUNG_CHO": "DoiTuongApDung",
}


def read_csv(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Khong doc duoc {path}")


def build_model(with_entities: bool) -> dict:
    """Dung mo hinh graph trong bo nho tu du lieu THAT (chua cham Neo4j)."""
    meta = read_csv(config.METADATA_CSV)
    rels = read_csv(config.RELATIONSHIPS_CSV)
    chunks = read_csv(config.CHUNKS_CSV)

    sk_by_docid = {m["id"]: m.get("so_ky_hieu", "") for m in meta}
    known_sk = {m.get("so_ky_hieu", "") for m in meta if m.get("so_ky_hieu")}

    vanban = []
    for m in meta:
        sk = m.get("so_ky_hieu") or m["id"]
        vanban.append(
            {
                "id": sk,
                "document_id": m["id"],
                "so_ky_hieu": sk,
                "title": m.get("title", ""),
                "document_type": m.get("loai_van_ban", ""),
                "status": m.get("tinh_trang_hieu_luc", ""),
                "effective_date": m.get("ngay_co_hieu_luc", ""),
                "issued_date": m.get("ngay_ban_hanh", ""),
                "issuing_body": m.get("co_quan_ban_hanh", ""),
                "signer": m.get("nguoi_ky", ""),
                "field": m.get("linh_vuc", ""),
                "in_corpus": True,
                "lab_session": config.LAB_SESSION,
            }
        )

    dieukhoan = []
    contains = []
    for c in chunks:
        sk = sk_by_docid.get(c["document_id"], c["document_id"])
        dieukhoan.append(
            {
                "id": c["chunk_id"],
                "document_id": c["document_id"],
                "so_ky_hieu": sk,
                "article": c.get("article", ""),
                "clause": c.get("clause", ""),
                "chapter": c.get("chapter", ""),
                "section": c.get("section", ""),
                "citation": c.get("citation", ""),
                "text": c.get("text", ""),
                "lab_session": config.LAB_SESSION,
            }
        )
        contains.append({"van_ban": sk, "dieu_khoan": c["chunk_id"]})

    # NEXT: theo dung thu tu chunk trong cung mot van ban (thu tu tu file corpus)
    by_doc: dict[str, list[str]] = defaultdict(list)
    for c in chunks:
        by_doc[c["document_id"]].append(c["chunk_id"])
    nexts = []
    for doc_id, ids in by_doc.items():
        for a, b in zip(ids, ids[1:]):
            nexts.append({"from": a, "to": b})

    doc_rels = []
    entity_rels = []
    entity_nodes: dict[str, dict] = {}
    skipped: Counter = Counter()
    external_docs: dict[str, dict] = {}

    for r in rels:
        rtype = r["relationship_type"]
        src, tgt = r["source"], r["target"]
        props = {
            "method": r.get("method", ""),
            "confidence": r.get("confidence", ""),
            "evidence": r.get("evidence", ""),
            "lab_session": config.LAB_SESSION,
        }
        if rtype in DOC_TO_DOC:
            if tgt not in known_sk:
                # Van ban duoc tham chieu nhung KHONG nam trong 30 van ban cua corpus.
                # Van tao node de khong mat quan he that, nhung danh dau in_corpus=false.
                external_docs.setdefault(
                    tgt,
                    {"id": tgt, "so_ky_hieu": tgt, "title": "", "document_type": "",
                     "status": "", "in_corpus": False, "lab_session": config.LAB_SESSION},
                )
            doc_rels.append({"from": src, "to": tgt, "type": rtype, "props": props})
        elif rtype in ENTITY_MAP:
            if not with_entities:
                skipped[rtype] += 1
                continue
            label = ENTITY_MAP[rtype]
            key = f"{label}:{tgt}"
            entity_nodes.setdefault(
                key, {"label": label, "id": tgt, "name": tgt,
                      "lab_session": config.LAB_SESSION}
            )
            entity_rels.append(
                {"from": src, "to": tgt, "type": rtype, "label": label, "props": props}
            )
        else:
            skipped[f"KHONG_XAC_DINH:{rtype}"] += 1

    return {
        "vanban": vanban,
        "external_docs": list(external_docs.values()),
        "dieukhoan": dieukhoan,
        "contains": contains,
        "nexts": nexts,
        "doc_rels": doc_rels,
        "entity_nodes": list(entity_nodes.values()),
        "entity_rels": entity_rels,
        "skipped": dict(skipped),
        "rel_type_counts": dict(Counter(r["relationship_type"] for r in rels)),
    }


def neo4j_ready() -> tuple[bool, str]:
    missing = [k for k, v in {
        "NEO4J_URI": config.NEO4J_URI,
        "NEO4J_USER": config.NEO4J_USER,
        "NEO4J_PASSWORD": config.NEO4J_PASSWORD,
    }.items() if not v]
    if missing:
        return False, f"Thieu cau hinh trong .env: {missing}"
    try:
        from neo4j import GraphDatabase  # noqa: F401
    except ImportError:
        return False, "Chua cai driver: pip install neo4j"
    return True, ""


def load_into_neo4j(model: dict, clean: bool) -> dict:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )
    driver.verify_connectivity()
    stats: dict = {}

    with driver.session(database=config.NEO4J_DATABASE) as s:
        for stmt in [
            "CREATE CONSTRAINT vanban_id_unique IF NOT EXISTS FOR (n:VanBan) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT dieukhoan_id_unique IF NOT EXISTS FOR (n:DieuKhoan) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX vanban_lab_session IF NOT EXISTS FOR (n:VanBan) ON (n.lab_session)",
            "CREATE INDEX dieukhoan_lab_session IF NOT EXISTS FOR (n:DieuKhoan) ON (n.lab_session)",
        ]:
            s.run(stmt)

        if clean:
            # CHI xoa du lieu cua buoi_14. Khong dung toi node cua buoi truoc.
            r = s.run(
                "MATCH (n) WHERE n.lab_session = $lab DETACH DELETE n "
                "RETURN count(*) AS deleted", lab=config.LAB_SESSION
            ).single()
            stats["deleted_buoi_14_nodes"] = r["deleted"] if r else 0

        r = s.run(
            "UNWIND $rows AS row MERGE (v:VanBan {id: row.id}) SET v += row "
            "RETURN count(*) AS n", rows=model["vanban"]
        ).single()
        stats["VanBan"] = r["n"]

        if model["external_docs"]:
            r = s.run(
                "UNWIND $rows AS row MERGE (v:VanBan {id: row.id}) "
                "ON CREATE SET v += row "
                "ON MATCH SET v.lab_session = coalesce(v.lab_session, row.lab_session) "
                "RETURN count(*) AS n", rows=model["external_docs"]
            ).single()
            stats["VanBan_ngoai_corpus"] = r["n"]

        total = 0
        rows = model["dieukhoan"]
        for i in range(0, len(rows), 500):
            r = s.run(
                "UNWIND $rows AS row MERGE (d:DieuKhoan {id: row.id}) SET d += row "
                "RETURN count(*) AS n", rows=rows[i:i + 500]
            ).single()
            total += r["n"]
        stats["DieuKhoan"] = total

        total = 0
        rows = model["contains"]
        for i in range(0, len(rows), 500):
            r = s.run(
                "UNWIND $rows AS row "
                "MATCH (v:VanBan {id: row.van_ban}), (d:DieuKhoan {id: row.dieu_khoan}) "
                "MERGE (v)-[c:CONTAINS]->(d) SET c.lab_session = $lab "
                "RETURN count(*) AS n", rows=rows[i:i + 500], lab=config.LAB_SESSION
            ).single()
            total += r["n"]
        stats["CONTAINS"] = total

        total = 0
        rows = model["nexts"]
        for i in range(0, len(rows), 500):
            r = s.run(
                "UNWIND $rows AS row "
                "MATCH (a:DieuKhoan {id: row.from}), (b:DieuKhoan {id: row.to}) "
                "MERGE (a)-[n:NEXT]->(b) SET n.lab_session = $lab "
                "RETURN count(*) AS n", rows=rows[i:i + 500], lab=config.LAB_SESSION
            ).single()
            total += r["n"]
        stats["NEXT"] = total

        for rtype in sorted({r["type"] for r in model["doc_rels"]}):
            batch = [r for r in model["doc_rels"] if r["type"] == rtype]
            r = s.run(
                f"UNWIND $rows AS row "
                f"MATCH (a:VanBan {{id: row.from}}), (b:VanBan {{id: row.to}}) "
                f"MERGE (a)-[rel:{rtype}]->(b) SET rel += row.props "
                f"RETURN count(*) AS n", rows=batch
            ).single()
            stats[rtype] = r["n"]

        if model["entity_nodes"]:
            for label in sorted({n["label"] for n in model["entity_nodes"]}):
                batch = [
                    {k: v for k, v in n.items() if k != "label"}
                    for n in model["entity_nodes"] if n["label"] == label
                ]
                r = s.run(
                    f"UNWIND $rows AS row MERGE (e:{label} {{id: row.id}}) SET e += row "
                    f"RETURN count(*) AS n", rows=batch
                ).single()
                stats[label] = r["n"]
            for rtype in sorted({r["type"] for r in model["entity_rels"]}):
                batch = [r for r in model["entity_rels"] if r["type"] == rtype]
                label = batch[0]["label"]
                r = s.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (a:VanBan {{id: row.from}}), (b:{label} {{id: row.to}}) "
                    f"MERGE (a)-[rel:{rtype}]->(b) SET rel += row.props "
                    f"RETURN count(*) AS n", rows=batch
                ).single()
                stats[rtype] = r["n"]

        # ---- kiem tra sau khi nap ----
        node_counts = {
            rec["loai"]: rec["n"] for rec in s.run(
                "MATCH (n {lab_session: $lab}) RETURN labels(n)[0] AS loai, count(*) AS n",
                lab=config.LAB_SESSION
            )
        }
        rel_counts = {
            rec["quan_he"]: rec["n"] for rec in s.run(
                "MATCH ({lab_session: $lab})-[r]->() RETURN type(r) AS quan_he, count(*) AS n",
                lab=config.LAB_SESSION
            )
        }
        orphans = {
            rec["loai"]: rec["n"] for rec in s.run(
                "MATCH (n {lab_session: $lab}) WHERE NOT (n)--() "
                "RETURN labels(n)[0] AS loai, count(*) AS n", lab=config.LAB_SESSION
            )
        }
        vb_no_dk = [
            rec["sk"] for rec in s.run(
                "MATCH (v:VanBan {lab_session: $lab}) WHERE NOT (v)-[:CONTAINS]->(:DieuKhoan) "
                "RETURN v.so_ky_hieu AS sk", lab=config.LAB_SESSION
            )
        ]
    driver.close()
    return {"written": stats, "node_counts": node_counts, "rel_counts": rel_counts,
            "orphans": orphans, "vanban_khong_co_dieu_khoan": vb_no_dk}


def write_report(model: dict, ran: bool, reason: str, result: dict | None) -> Path:
    L: list[str] = []
    add = L.append
    add("# Bao cao xay Mini Knowledge Graph - Buoi 14\n")
    add(f"- Nguon (chi doc): `{config.KB_DIR}`")
    add(f"- Corpus: `data/processed/chunks_normalized.csv`")
    add(f"- Nhan phan biet buoi hoc: `lab_session = \"{config.LAB_SESSION}\"`\n")

    add("## 1. relationship_type CO THAT trong `relationships.csv`\n")
    add("| relationship_type | So dong | Xu ly |")
    add("|---|---|---|")
    for t, c in sorted(model["rel_type_counts"].items(), key=lambda kv: -kv[1]):
        if t in DOC_TO_DOC:
            how = "**NAP** - target la so_ky_hieu -> (:VanBan)-[:%s]->(:VanBan)" % t
        elif t in ENTITY_MAP:
            how = (f"target la thuc the `{ENTITY_MAP[t]}`, KHONG phai van ban -> "
                   f"chi nap khi chay `--with-entities`")
        else:
            how = "khong xac dinh - KHONG nap"
        add(f"| `{t}` | {c} | {how} |")
    add("")
    add("> Khong tao them bat ky relation type nao ngoai danh sach tren. "
        "`CONTAINS` va `NEXT` khong den tu suy doan ma den tu **cau truc that** cua "
        "van ban: `CONTAINS` = chunk thuoc van ban nao, `NEXT` = thu tu Dieu/khoan "
        "trong cung mot van ban.\n")

    add("## 2. Mo hinh graph da dung (truoc khi nap)\n")
    add(f"- Node `VanBan` (trong corpus): **{len(model['vanban'])}**")
    add(f"- Node `VanBan` (duoc tham chieu nhung ngoai corpus, `in_corpus=false`): "
        f"**{len(model['external_docs'])}**")
    add(f"- Node `DieuKhoan`: **{len(model['dieukhoan'])}**")
    add(f"- Quan he `CONTAINS`: **{len(model['contains'])}**")
    add(f"- Quan he `NEXT`: **{len(model['nexts'])}**")
    add(f"- Quan he van ban - van ban: **{len(model['doc_rels'])}** "
        f"({dict(Counter(r['type'] for r in model['doc_rels']))})")
    if model["entity_rels"]:
        add(f"- Quan he van ban - thuc the: **{len(model['entity_rels'])}** "
            f"({dict(Counter(r['type'] for r in model['entity_rels']))})")
    if model["skipped"]:
        add(f"- Bo qua co chu dich: {model['skipped']}")
    add("")

    add("## 3. Ket qua nap vao Neo4j\n")
    if not ran:
        add("```")
        add("NOT RUN")
        add("```")
        add(f"**Ly do:** {reason}\n")
        add("Cach chay lai khi Neo4j da san sang:\n")
        add("```bash")
        add("# 1. Tao buoi_14/.env tu .env.example va dien NEO4J_*")
        add("# 2. pip install neo4j")
        add("python scripts/load_mini_kg.py")
        add("```")
        add("\nPhan Retrieval (BM25 / Dense / Hybrid / Rerank / Streamlit) **khong bi anh huong** "
            "boi viec Neo4j chua chay.\n")
    else:
        add("```")
        add("RUN OK")
        add("```")
        add("### Da ghi (MERGE, chay lai khong tao duplicate)\n")
        add("| Doi tuong | So luong |")
        add("|---|---|")
        for k, v in result["written"].items():
            add(f"| {k} | {v} |")
        add("")
        add("### Dem lai tu database (chi `lab_session = buoi_14`)\n")
        add("| Label | So node |")
        add("|---|---|")
        for k, v in sorted(result["node_counts"].items()):
            add(f"| {k} | {v} |")
        add("")
        add("| Quan he | So luong |")
        add("|---|---|")
        for k, v in sorted(result["rel_counts"].items()):
            add(f"| {k} | {v} |")
        add("")
        add("### Kiem tra chat luong\n")
        add(f"- Node khong co lien ket nao (orphan): "
            f"{result['orphans'] if result['orphans'] else 'khong co'}")
        add(f"- Van ban khong co dieu khoan nao: "
            f"{result['vanban_khong_co_dieu_khoan'] or 'khong co'}")
        add("")

    add("## 4. An toan du lieu\n")
    add("- Khong chay `MATCH (n) DETACH DELETE n` trong bat ky truong hop nao.")
    add("- Chi dung `MERGE` theo `id` -> chay lai nhieu lan khong tao ban ghi trung.")
    add("- Toan bo node/quan he cua bai nay mang `lab_session = \"buoi_14\"`, "
        "nen du lieu cac buoi truoc trong cung database khong bi dung toi.")
    add("- Muon xoa rieng du lieu Buoi 14: `python scripts/load_mini_kg.py --clean --yes`.")

    path = config.OUTPUTS_DIR / "kg_build_report.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-entities", action="store_true",
                    help="nap them quan he van ban -> nguoi ky / co quan / linh vuc / doi tuong")
    ap.add_argument("--clean", action="store_true",
                    help="XOA truoc khi nap - CHI node co lab_session='buoi_14'")
    ap.add_argument("--yes", action="store_true", help="xac nhan cho --clean")
    ap.add_argument("--dry-run", action="store_true", help="chi dung mo hinh, khong cham Neo4j")
    args = ap.parse_args()

    if args.clean and not args.yes:
        print("[DUNG] --clean se xoa toan bo node co lab_session='buoi_14'.")
        print("       Them --yes de xac nhan. (Du lieu buoi khac KHONG bi dung toi.)")
        return 2

    print("=" * 74)
    print("PROMPT 6 - MINI KNOWLEDGE GRAPH")
    print("=" * 74)
    model = build_model(with_entities=args.with_entities)
    print(f"VanBan               : {len(model['vanban'])} (+{len(model['external_docs'])} ngoai corpus)")
    print(f"DieuKhoan            : {len(model['dieukhoan'])}")
    print(f"CONTAINS             : {len(model['contains'])}")
    print(f"NEXT                 : {len(model['nexts'])}")
    print(f"Quan he VanBan-VanBan: {len(model['doc_rels'])} "
          f"{dict(Counter(r['type'] for r in model['doc_rels']))}")
    if model["skipped"]:
        print(f"Bo qua co chu dich   : {model['skipped']}")
    print()

    if args.dry_run:
        path = write_report(model, False, "Chay voi --dry-run, khong ket noi Neo4j", None)
        print(f"Da ghi: {path.relative_to(config.BASE_DIR)}")
        return 0

    ready, reason = neo4j_ready()
    result = None
    if ready:
        try:
            result = load_into_neo4j(model, clean=args.clean)
            print("Da nap vao Neo4j:")
            for k, v in result["written"].items():
                print(f"  {k:<28} {v}")
        except Exception as exc:  # noqa: BLE001
            ready = False
            reason = f"Khong ket noi/nap duoc Neo4j: {type(exc).__name__}: {str(exc)[:250]}"
            print(f"[LOI] {reason}")
    if not ready:
        print("=" * 74)
        print("NEO4J CHUA SAN SANG - kg_build_report.md se ghi NOT RUN")
        print("=" * 74)
        print(f"  Ly do: {reason}")
        print("  Tao buoi_14/.env tu .env.example, dien NEO4J_URI/USER/PASSWORD/DATABASE,")
        print("  cai `pip install neo4j`, dam bao Neo4j dang chay roi chay lai script nay.")
        print("  Cac phan Retrieval/Streamlit KHONG bi anh huong.")

    path = write_report(model, ready and result is not None, reason, result)
    print(f"\nDa ghi: {path.relative_to(config.BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
