#!/usr/bin/env python3
"""
Buoc 2 - Chuan hoa 4 CSV nghiep vu thanh outputs/entities.csv va outputs/relations.csv.

Quy tac bat buoc:
  - Khong tu sinh them quan he ngoai relationships_seed.csv.
  - Khong tu doi PROPOSED thanh VERIFIED (giu nguyen verification_status goc).
  - Khong suy luan ten don vi tu owner_unit_id.
  - Khong suy luan ten vai tro tu owner_role_id.
  - Kiem tra source_id / target_id trong relations deu phai ton tai trong entities.
"""

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(exist_ok=True)

RISK_FILE = DATA_DIR / "risk_profiles_seed.csv"
CONTROL_FILE = DATA_DIR / "controls_seed.csv"
EVENT_FILE = DATA_DIR / "risk_events_seed.csv"
REL_FILE = DATA_DIR / "relationships_seed.csv"

ENTITIES_OUT = OUT_DIR / "entities.csv"
RELATIONS_OUT = OUT_DIR / "relations.csv"

# Cot chung + cot nghiep vu rieng cua tung loai entity (giu nguyen du lieu goc, khong lam mat thong tin)
ENTITY_COLUMNS = [
    "id", "type", "name", "description", "source_file", "data_origin", "verification_status",
    # RuiRo
    "category", "cause", "event", "impact", "inherent_level", "residual_level", "owner_unit_id",
    # KiemSoat
    "control_type", "frequency", "owner_role_id", "effectiveness",
    # SuKienRuiRo
    "risk_id", "occurred_at", "discovered_at", "severity", "loss_amount_vnd",
]

RELATION_COLUMNS = [
    "source_id", "relationship_type", "target_id",
    "source", "evidence_quote", "confidence", "verification_status", "data_origin",
]


def read_csv(path: Path):
    if not path.exists():
        print(f"  [LOI] Khong tim thay file: {path}")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def blank_row():
    return {c: "" for c in ENTITY_COLUMNS}


def build_entities():
    entities = []

    for row in read_csv(RISK_FILE):
        e = blank_row()
        e.update({
            "id": row.get("id", ""),
            "type": "RuiRo",
            "name": row.get("name", ""),
            "description": row.get("description", ""),
            "source_file": RISK_FILE.name,
            "data_origin": row.get("data_origin", ""),
            "verification_status": row.get("verification_status", ""),
            "category": row.get("category", ""),
            "cause": row.get("cause", ""),
            "event": row.get("event", ""),
            "impact": row.get("impact", ""),
            "inherent_level": row.get("inherent_level", ""),
            "residual_level": row.get("residual_level", ""),
            "owner_unit_id": row.get("owner_unit_id", ""),
        })
        entities.append(e)

    for row in read_csv(CONTROL_FILE):
        e = blank_row()
        e.update({
            "id": row.get("id", ""),
            "type": "KiemSoat",
            "name": row.get("name", ""),
            "description": "",  # controls_seed.csv khong co cot description rieng
            "source_file": CONTROL_FILE.name,
            "data_origin": row.get("data_origin", ""),
            "verification_status": row.get("verification_status", ""),
            "control_type": row.get("control_type", ""),
            "frequency": row.get("frequency", ""),
            "owner_role_id": row.get("owner_role_id", ""),
            "effectiveness": row.get("effectiveness", ""),
        })
        entities.append(e)

    for row in read_csv(EVENT_FILE):
        e = blank_row()
        e.update({
            "id": row.get("id", ""),
            "type": "SuKienRuiRo",
            "name": row.get("description", ""),  # events khong co truong name rieng, dung description
            "description": row.get("description", ""),
            "source_file": EVENT_FILE.name,
            "data_origin": row.get("data_origin", ""),
            "verification_status": row.get("verification_status", ""),
            "risk_id": row.get("risk_id", ""),
            "occurred_at": row.get("occurred_at", ""),
            "discovered_at": row.get("discovered_at", ""),
            "severity": row.get("severity", ""),
            "loss_amount_vnd": row.get("loss_amount_vnd", ""),
        })
        entities.append(e)

    return entities


def build_relations():
    relations = []
    for row in read_csv(REL_FILE):
        r = {c: row.get(c, "") for c in RELATION_COLUMNS}
        relations.append(r)
    return relations


def write_csv(path: Path, rows, columns):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    print("=" * 70)
    print("BUOC 2 - CHUAN HOA DU LIEU THANH entities.csv / relations.csv")
    print("=" * 70)

    entities = build_entities()
    relations = build_relations()

    write_csv(ENTITIES_OUT, entities, ENTITY_COLUMNS)
    write_csv(RELATIONS_OUT, relations, RELATION_COLUMNS)

    entity_ids = {e["id"] for e in entities}

    # Thong ke entity theo type
    type_counts = {}
    for e in entities:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1
    print("\nSo entity theo tung type:")
    for t, c in type_counts.items():
        print(f"  {t}: {c}")

    # Thong ke relation theo relationship_type
    rel_counts = {}
    for r in relations:
        rel_counts[r["relationship_type"]] = rel_counts.get(r["relationship_type"], 0) + 1
    print("\nSo relation theo tung relationship_type:")
    for t, c in rel_counts.items():
        print(f"  {t}: {c}")

    # Kiem tra orphan reference: source_id / target_id khong ton tai trong entities.csv
    orphans = []
    for r in relations:
        if r["source_id"] not in entity_ids:
            orphans.append(("source_id", r["source_id"], r["relationship_type"]))
        if r["target_id"] not in entity_ids:
            orphans.append(("target_id", r["target_id"], r["relationship_type"]))

    print("\nKiem tra orphan reference (source_id/target_id khong ton tai trong entities.csv):")
    if orphans:
        for kind, val, rel_type in orphans:
            print(f"  [LOI] {kind}='{val}' (relationship_type={rel_type}) khong ton tai trong entities.csv")
    else:
        print("  Khong co orphan reference.")

    # Kiem tra khong tu doi verification_status: so sanh voi file goc
    print("\nKiem tra bao toan verification_status goc cua relations:")
    src_rel_rows = read_csv(REL_FILE)
    mismatch = 0
    for orig, new in zip(src_rel_rows, relations):
        if orig.get("verification_status", "") != new.get("verification_status", ""):
            mismatch += 1
    print(f"  So dong bi thay doi verification_status so voi file goc: {mismatch}")

    print(f"\nDa ghi: {ENTITIES_OUT.relative_to(BASE_DIR)} ({len(entities)} dong)")
    print(f"Da ghi: {RELATIONS_OUT.relative_to(BASE_DIR)} ({len(relations)} dong)")

    ok = len(orphans) == 0 and mismatch == 0
    print(f"\nKET LUAN: {'DAT' if ok else 'CHUA DAT - can kiem tra lai du lieu'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
