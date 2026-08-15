#!/usr/bin/env python3
"""
Buoc 4 - Kiem thu Wiki Risk Graph vua tao.

Kiem tra toi thieu:
  1. Tong so file Markdown.
  2. Tong so wikilink.
  3. Wikilink tro toi trang khong ton tai.
  4. Entity bi trung ID.
  5. Trang co ID nhung khong ton tai trong entities.csv.
  6. Relation co source hoac target khong ton tai.
  7. RuiRo khong co bat ky KiemSoat nao.
  8. RuiRo khong co bat ky SuKienRuiRo nao.
  9. Trang khong co lien ket voi trang khac (orphan page).

KHONG sua du lieu bang cach bia them quan he. Chi bao cao.
Bao cao phai phan biet: loi do CODE build_wiki.py gay ra (broken link do build sai)
so voi loi/khoang trong DU LIEU (vi du rui ro chua co kiem soat trong bo du lieu goc).
"""

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs"
WIKI_DIR = BASE_DIR / "wiki"

ENTITIES_CSV = OUT_DIR / "entities.csv"
RELATIONS_CSV = OUT_DIR / "relations.csv"
REPORT_MD = OUT_DIR / "wiki_validation_report.md"

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
FRONTMATTER_ID_RE = re.compile(r"^id:\s*(.+)$", re.MULTILINE)


def read_csv(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_md_files():
    return sorted(WIKI_DIR.rglob("*.md"))


def page_id_from_path(path: Path) -> str:
    """ID cua trang = ten file (khong duoi .md), tru Home.md."""
    return path.stem


def main():
    entities = read_csv(ENTITIES_CSV)
    relations = read_csv(RELATIONS_CSV)
    entity_ids = {e["id"] for e in entities}
    entity_by_id = {e["id"]: e for e in entities}

    md_files = find_md_files()
    total_md = len(md_files)

    # id -> path, cho tat ca trang wiki (khong tinh Home.md la mot "entity")
    page_ids = {}
    for p in md_files:
        if p.name == "Home.md":
            continue
        page_ids[page_id_from_path(p)] = p

    # --- 1 & 2: dem file, dem wikilink; thu thap outgoing links tung trang ---
    outgoing = defaultdict(set)  # page_key -> set(target_id)
    total_wikilinks = 0
    contents = {}
    for p in md_files:
        text = p.read_text(encoding="utf-8")
        contents[p] = text
        links = WIKILINK_RE.findall(text)
        total_wikilinks += len(links)
        key = "Home" if p.name == "Home.md" else page_id_from_path(p)
        outgoing[key] = set(links)

    # --- 3: broken link = wikilink tro toi ID khong co trang tuong ung ---
    broken_links = []  # (trang_nguon, target_id)
    for p in md_files:
        key = "Home" if p.name == "Home.md" else page_id_from_path(p)
        for target in outgoing[key]:
            if target != "Home" and target not in page_ids:
                broken_links.append((key, target))

    # --- 4: entity bi trung ID (trong entities.csv) ---
    id_counter = Counter(e["id"] for e in entities)
    duplicate_entity_ids = [eid for eid, c in id_counter.items() if c > 1]

    # --- 5: trang co ID (frontmatter) nhung khong co trong entities.csv ---
    pages_without_entity = []
    for pid, path in page_ids.items():
        fm_match = FRONTMATTER_ID_RE.search(contents[path])
        fm_id = fm_match.group(1).strip() if fm_match else pid
        if fm_id not in entity_ids:
            pages_without_entity.append((fm_id, str(path.relative_to(BASE_DIR))))

    # --- 6: relation co source/target khong ton tai trong entities.csv ---
    bad_relations = []
    for r in relations:
        if r["source_id"] not in entity_ids:
            bad_relations.append(("source_id", r["source_id"], r["relationship_type"], r["target_id"]))
        if r["target_id"] not in entity_ids:
            bad_relations.append(("target_id", r["target_id"], r["relationship_type"], r["source_id"]))

    # --- 7 & 8: RuiRo thieu KiemSoat / thieu SuKienRuiRo ---
    risks = [e for e in entities if e["type"] == "RuiRo"]
    risk_ids_with_control = {r["target_id"] for r in relations if r["relationship_type"] == "MITIGATES"}
    risk_ids_with_event = {r["source_id"] for r in relations if r["relationship_type"] == "OBSERVED_AS"}

    risks_without_control = [r["id"] for r in risks if r["id"] not in risk_ids_with_control]
    risks_without_event = [r["id"] for r in risks if r["id"] not in risk_ids_with_event]

    # --- 9: orphan page = khong co outgoing link nao VA khong co incoming link nao (tru Home.md) ---
    incoming = defaultdict(set)
    for src_key, targets in outgoing.items():
        for t in targets:
            incoming[t].add(src_key)

    orphan_pages = []
    for pid, path in page_ids.items():
        has_outgoing = len(outgoing.get(pid, set())) > 0
        # incoming tu cac trang KHAC Home.md (Home luon link toi moi trang nen khong tinh)
        incoming_non_home = {s for s in incoming.get(pid, set()) if s != "Home"}
        if not has_outgoing and not incoming_non_home:
            orphan_pages.append(pid)

    # ================= PHAN LOAI LOI: CODE vs DU LIEU =================
    code_errors = []
    data_gaps = []

    if broken_links:
        code_errors.append(f"Wikilink hong (broken link): {len(broken_links)} truong hop -> "
                            f"loi chuong trinh build_wiki.py (sinh link toi ID khong ton tai trang).")
    if duplicate_entity_ids:
        code_errors.append(f"Entity bi trung ID trong entities.csv: {duplicate_entity_ids} -> "
                            f"loi du lieu dau vao hoac loi build_entities.py khi gop du lieu.")
    if pages_without_entity:
        code_errors.append(f"Trang wiki co ID khong khop entities.csv: {len(pages_without_entity)} trang -> "
                            f"loi chuong trinh build_wiki.py.")
    if bad_relations:
        code_errors.append(f"Relation tham chieu ID khong ton tai: {len(bad_relations)} truong hop -> "
                            f"loi du lieu nguon relationships_seed.csv hoac loi build_entities.py.")

    if risks_without_control:
        data_gaps.append(f"RuiRo chua co KiemSoat nao trong bo du lieu: {risks_without_control} "
                          f"-> day la khoang trong DU LIEU (chua co kiem soat duoc ghi nhan), khong phai loi code.")
    if risks_without_event:
        data_gaps.append(f"RuiRo chua co SuKienRuiRo nao trong bo du lieu: {risks_without_event} "
                          f"-> day la khoang trong DU LIEU (rui ro chua xay ra su kien thuc te), khong phai loi code.")
    if orphan_pages:
        data_gaps.append(f"Trang khong co lien ket nao (orphan): {orphan_pages} "
                          f"-> thuong la RuiRo chua co ca kiem soat lan su kien trong du lieu goc, khong phai loi code.")

    # ================= GHI BAO CAO =================
    lines = []
    lines.append("# Bao cao kiem thu Wiki Risk Graph\n")
    lines.append("## 1. Thong ke tong quat\n")
    lines.append(f"- Tong so file Markdown: {total_md}")
    lines.append(f"- Tong so wikilink: {total_wikilinks}")
    lines.append(f"- Tong so entity (entities.csv): {len(entities)}")
    lines.append(f"- Tong so relation (relations.csv): {len(relations)}\n")

    lines.append("## 2. Wikilink hong (broken link)\n")
    if broken_links:
        for src, tgt in broken_links:
            lines.append(f"- Trang `{src}` link toi `[[{tgt}]]` nhung khong co trang tuong ung.")
    else:
        lines.append("Khong co wikilink hong.")
    lines.append("")

    lines.append("## 3. Entity bi trung ID\n")
    lines.append(f"{duplicate_entity_ids if duplicate_entity_ids else 'Khong co.'}\n")

    lines.append("## 4. Trang co ID nhung khong ton tai trong entities.csv\n")
    if pages_without_entity:
        for fm_id, path in pages_without_entity:
            lines.append(f"- ID `{fm_id}` (trang `{path}`)")
    else:
        lines.append("Khong co.")
    lines.append("")

    lines.append("## 5. Relation co source/target khong ton tai\n")
    if bad_relations:
        for kind, val, rel_type, other in bad_relations:
            lines.append(f"- {kind}=`{val}` (relationship_type={rel_type}) khong ton tai trong entities.csv")
    else:
        lines.append("Khong co.")
    lines.append("")

    lines.append("## 6. RuiRo khong co KiemSoat nao\n")
    lines.append(f"{risks_without_control if risks_without_control else 'Khong co (moi RuiRo deu co it nhat mot KiemSoat).'}\n")

    lines.append("## 7. RuiRo khong co SuKienRuiRo nao\n")
    lines.append(f"{risks_without_event if risks_without_event else 'Khong co (moi RuiRo deu co it nhat mot SuKienRuiRo).'}\n")

    lines.append("## 8. Trang khong co lien ket voi trang khac (orphan page)\n")
    lines.append(f"{orphan_pages if orphan_pages else 'Khong co.'}\n")

    lines.append("## 9. Phan loai loi: CODE vs DU LIEU\n")
    lines.append("### Loi do chuong trinh (build_wiki.py / build_entities.py)\n")
    if code_errors:
        for e in code_errors:
            lines.append(f"- {e}")
    else:
        lines.append("Khong phat hien loi chuong trinh.")
    lines.append("")
    lines.append("### Khoang trong du lieu (khong phai loi code, can bo sung du lieu neu muon day du hon)\n")
    if data_gaps:
        for e in data_gaps:
            lines.append(f"- {e}")
    else:
        lines.append("Khong co khoang trong du lieu dang ke.")
    lines.append("")

    overall_ok = not (broken_links or duplicate_entity_ids or pages_without_entity or bad_relations)
    lines.append("## 10. Ket luan\n")
    lines.append(f"- Loi chuong trinh (can Agent tu sua): {'CO' if not overall_ok else 'KHONG'}")
    lines.append(f"- Khoang trong du lieu (can bo sung du lieu, KHONG duoc tu bia): "
                  f"{'CO' if data_gaps else 'KHONG'}")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    # ================= IN RA CONSOLE =================
    print("=" * 70)
    print("BUOC 4 - KIEM THU WIKI")
    print("=" * 70)
    print(f"Tong so file Markdown: {total_md}")
    print(f"Tong so wikilink: {total_wikilinks}")
    print(f"Broken link: {len(broken_links)}")
    print(f"Entity trung ID: {len(duplicate_entity_ids)}")
    print(f"Trang co ID khong khop entities.csv: {len(pages_without_entity)}")
    print(f"Relation tham chieu ID khong ton tai: {len(bad_relations)}")
    print(f"RuiRo khong co KiemSoat: {risks_without_control}")
    print(f"RuiRo khong co SuKienRuiRo: {risks_without_event}")
    print(f"Orphan page: {orphan_pages}")
    print(f"\nDa ghi bao cao: {REPORT_MD.relative_to(BASE_DIR)}")

    print(f"\nLoi chuong trinh: {'CO - CAN SUA' if not overall_ok else 'KHONG CO'}")
    print(f"Khoang trong du lieu: {'CO (khong phai loi code)' if data_gaps else 'KHONG'}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
