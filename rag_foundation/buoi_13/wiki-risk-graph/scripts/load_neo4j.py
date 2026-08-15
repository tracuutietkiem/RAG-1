#!/usr/bin/env python3
"""
Buoc 6 - Nap outputs/entities.csv va outputs/relations.csv vao Neo4j.

- Doc cau hinh ket noi tu file .env (KHONG hard-code password):
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE
- Dung MERGE + id lam khoa duy nhat de chay lai nhieu lan khong tao duplicate.
- Dung parameterized Cypher (khong noi chuoi truc tiep gia tri vao cau lenh).
- Neu Neo4j chua chay hoac thieu driver, in huong dan ro rang va thoat an toan,
  KHONG dong den cac file Wiki/entities/relations da tao o cac buoc truoc.
"""

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs"
ENTITIES_CSV = OUT_DIR / "entities.csv"
RELATIONS_CSV = OUT_DIR / "relations.csv"
ENV_FILE = BASE_DIR / ".env"

REQUIRED_ENV_KEYS = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"]


def load_env(path: Path) -> dict:
    """Doc file .env don gian (KEY=VALUE moi dong), khong can them thu vien ngoai."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def read_csv(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def print_setup_instructions(missing_keys=None, driver_missing=False):
    print("=" * 70)
    print("NEO4J CHUA SAN SANG - HUONG DAN THIET LAP")
    print("=" * 70)
    if driver_missing:
        print("  - Chua cai dat Python driver cho Neo4j. Cai bang:")
        print("      pip install neo4j")
    if missing_keys:
        print(f"  - Thieu cau hinh trong file .env: {missing_keys}")
        print("  - Tao file .env tai thu muc goc project voi noi dung mau:")
        print("      NEO4J_URI=bolt://localhost:7687")
        print("      NEO4J_USER=neo4j")
        print("      NEO4J_PASSWORD=<mat_khau_cua_ban>")
        print("      NEO4J_DATABASE=neo4j")
    print("  - Dam bao Neo4j Desktop / Docker container dang chay truoc khi thu lai.")
    print("  - Cac buoc Wiki (1-4) va file Wiki da tao KHONG bi anh huong boi buoc nay.")
    print("  - Sau khi cau hinh xong, chay lai:")
    print("      python3 scripts/load_neo4j.py")


def main():
    env = load_env(ENV_FILE)
    missing = [k for k in REQUIRED_ENV_KEYS if not env.get(k)]
    if missing:
        print_setup_instructions(missing_keys=missing)
        return 0  # khong bao loi nghiem trong, chi la chua cau hinh

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print_setup_instructions(driver_missing=True)
        return 0

    uri = env["NEO4J_URI"]
    user = env["NEO4J_USER"]
    password = env["NEO4J_PASSWORD"]
    database = env["NEO4J_DATABASE"]

    entities = read_csv(ENTITIES_CSV)
    relations = read_csv(RELATIONS_CSV)
    if not entities:
        print("  [LOI] Khong co outputs/entities.csv. Hay chay build_entities.py truoc.")
        return 1

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001 - can bao loi ket noi ro rang cho nguoi dung
        print("  [LOI] Khong ket noi duoc Neo4j:")
        print(f"    {exc}")
        print_setup_instructions()
        return 0

    label_map = {"RuiRo": "RuiRo", "KiemSoat": "KiemSoat", "SuKienRuiRo": "SuKienRuiRo"}

    def merge_entity(tx, label, props):
        # Dung parameterized Cypher, id la khoa duy nhat, MERGE khong tao duplicate
        query = f"MERGE (n:{label} {{id: $id}}) SET n += $props"
        tx.run(query, id=props["id"], props=props)

    def merge_relation(tx, src_label, tgt_label, rel_type, source_id, target_id, props):
        query = (
            f"MATCH (a:{src_label} {{id: $source_id}}), (b:{tgt_label} {{id: $target_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"SET r += $props"
        )
        tx.run(query, source_id=source_id, target_id=target_id, props=props)

    node_counts = {"RuiRo": 0, "KiemSoat": 0, "SuKienRuiRo": 0}
    rel_counts = {"MITIGATES": 0, "OBSERVED_AS": 0}

    with driver.session(database=database) as session:
        for e in entities:
            label = label_map.get(e["type"])
            if not label:
                continue
            props = {k: v for k, v in e.items() if v != ""}
            session.execute_write(merge_entity, label, props)
            node_counts[label] += 1

        for r in relations:
            rel_type = r["relationship_type"]
            props = {k: v for k, v in r.items() if v != ""}
            if rel_type == "MITIGATES":
                session.execute_write(merge_relation, "KiemSoat", "RuiRo", "MITIGATES",
                                       r["source_id"], r["target_id"], props)
                rel_counts["MITIGATES"] += 1
            elif rel_type == "OBSERVED_AS":
                session.execute_write(merge_relation, "RuiRo", "SuKienRuiRo", "OBSERVED_AS",
                                       r["source_id"], r["target_id"], props)
                rel_counts["OBSERVED_AS"] += 1
            else:
                print(f"  [CANH BAO] Bo qua relationship_type khong xac dinh: {rel_type}")

    driver.close()

    print("=" * 70)
    print("DA NAP DU LIEU VAO NEO4J")
    print("=" * 70)
    print(f"  Node: {node_counts}")
    print(f"  Relation: {rel_counts}")
    print("  Chay lai script nay bao nhieu lan cung an toan (dung MERGE).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
