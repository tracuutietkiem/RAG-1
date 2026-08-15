#!/usr/bin/env python3
"""
Buoc 1 - Kiem tra du lieu nguon cho Wiki Risk Graph.

Doc that 4 file CSV va bao cao:
  - so dong, ten cot
  - khoa chinh
  - khoa tham chieu
  - cac loai relationship_type
  - so gia tri null theo cot
  - duplicate id
  - khoa tham chieu bi thieu (orphan reference)

Khong tao Wiki o buoc nay. Chi doc va bao cao thuc te.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

FILES = {
    "risk_profiles": DATA_DIR / "risk_profiles_seed.csv",
    "controls": DATA_DIR / "controls_seed.csv",
    "risk_events": DATA_DIR / "risk_events_seed.csv",
    "relationships": DATA_DIR / "relationships_seed.csv",
}

PRIMARY_KEYS = {
    "risk_profiles": "id",
    "controls": "id",
    "risk_events": "id",
    "relationships": None,  # khong co khoa chinh don, la bang canh (edge)
}


def read_csv(path: Path):
    if not path.exists():
        print(f"  [LOI] Khong tim thay file: {path}")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def report_nulls(rows, columns):
    null_counts = Counter()
    for row in rows:
        for col in columns:
            val = (row.get(col) or "").strip()
            if val == "":
                null_counts[col] += 1
    return null_counts


def report_duplicates(rows, key_field):
    if not key_field:
        return []
    counts = Counter(row.get(key_field, "") for row in rows)
    return [k for k, c in counts.items() if c > 1 and k != ""]


def main():
    print("=" * 70)
    print("BAO CAO KIEM TRA DU LIEU - WIKI RISK GRAPH")
    print("=" * 70)

    datasets = {}
    for name, path in FILES.items():
        rows = read_csv(path)
        datasets[name] = rows
        print(f"\n--- {path.name} ---")
        if not rows:
            print("  Khong co du lieu hoac file khong ton tai.")
            continue
        columns = list(rows[0].keys())
        print(f"  So dong: {len(rows)}")
        print(f"  Cac cot: {columns}")

        key_field = PRIMARY_KEYS.get(name)
        if key_field:
            dups = report_duplicates(rows, key_field)
            print(f"  Khoa chinh: {key_field}")
            print(f"  Duplicate {key_field}: {dups if dups else 'khong co'}")

        nulls = report_nulls(rows, columns)
        nulls_report = {c: nulls.get(c, 0) for c in columns if nulls.get(c, 0) > 0}
        print(f"  So gia tri null theo cot: {nulls_report if nulls_report else 'khong co'}")

    # --- Phan tich rieng relationships ---
    print("\n" + "=" * 70)
    print("PHAN TICH quan he (relationships_seed.csv)")
    print("=" * 70)
    rel_rows = datasets.get("relationships", [])
    rel_types = Counter(r.get("relationship_type", "") for r in rel_rows)
    print(f"  Cac loai relationship_type va so luong: {dict(rel_types)}")

    # Tap hop id hop le tu 3 nguon entity
    risk_ids = {r["id"] for r in datasets.get("risk_profiles", []) if r.get("id")}
    control_ids = {r["id"] for r in datasets.get("controls", []) if r.get("id")}
    event_ids = {r["id"] for r in datasets.get("risk_events", []) if r.get("id")}
    all_entity_ids = risk_ids | control_ids | event_ids

    missing_refs = []
    for r in rel_rows:
        src, tgt = r.get("source_id", ""), r.get("target_id", "")
        if src not in all_entity_ids:
            missing_refs.append(("source_id", src, r.get("relationship_type")))
        if tgt not in all_entity_ids:
            missing_refs.append(("target_id", tgt, r.get("relationship_type")))

    print(f"  Khoa tham chieu bi thieu (source_id/target_id khong ton tai trong entity): "
          f"{missing_refs if missing_refs else 'khong co'}")

    # --- Kiem tra owner_unit_id / owner_role_id la ma tham chieu chua co master data ---
    print("\n" + "=" * 70)
    print("GHI CHU VE DU LIEU CHUA CO (KHONG TU BIA)")
    print("=" * 70)
    owner_units = sorted({r.get("owner_unit_id", "") for r in datasets.get("risk_profiles", []) if r.get("owner_unit_id")})
    owner_roles = sorted({r.get("owner_role_id", "") for r in datasets.get("controls", []) if r.get("owner_role_id")})
    print(f"  owner_unit_id xuat hien trong risk_profiles: {owner_units}")
    print(f"  -> Day chi la MA don vi. Chua co file master units.csv de tra ten don vi. Chua co du lieu.")
    print(f"  owner_role_id xuat hien trong controls: {owner_roles}")
    print(f"  -> Day chi la MA vai tro. Chua co file master roles.csv de tra ten vai tro. Chua co du lieu.")
    print("  Cac loai node/edge sau CHUA co du lieu nguon: VanBan, DieuKhoan, QuyTrinh.")

    # --- De xuat kien truc MVP ---
    print("\n" + "=" * 70)
    print("DE XUAT KIEN TRUC MVP")
    print("=" * 70)
    print("  Node:")
    print(f"    RuiRo         (tu risk_profiles_seed.csv)   - {len(risk_ids)} node")
    print(f"    KiemSoat      (tu controls_seed.csv)         - {len(control_ids)} node")
    print(f"    SuKienRuiRo   (tu risk_events_seed.csv)      - {len(event_ids)} node")
    print("  Edge:")
    print("    KiemSoat -MITIGATES-> RuiRo")
    print("    RuiRo -OBSERVED_AS-> SuKienRuiRo")
    print("  Luong: KiemSoat -> RuiRo -> SuKienRuiRo")

    print("\n" + "=" * 70)
    print("KET LUAN")
    print("=" * 70)
    ok = len(missing_refs) == 0
    print(f"  Tinh toan ven tham chieu: {'DAT' if ok else 'CHUA DAT - can kiem tra lai relationships_seed.csv'}")
    print("  San sang cho Buoc 2: chuan hoa entities.csv / relations.csv")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
