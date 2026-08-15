#!/usr/bin/env python3
"""
Buoc 3 - Sinh Wiki Markdown (Obsidian) tu outputs/entities.csv va outputs/relations.csv.

Quy tac bat buoc:
  - Khong tu tao quan he ngoai relations.csv.
  - Khong bia ten owner_unit_id / owner_role_id (chi hien thi ma, ghi ro "Chua co du lieu.").
  - Ten file dung ID (an toan, khong dau/khoang trang) + wikilink dang [[ID|Ten hien thi]]
    de dam bao link hoat dong chinh xac trong Obsidian du ten entity co dau tieng Viet.
  - Neu thieu du lieu phai ghi ro: "Chua co du lieu."
"""

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs"
WIKI_DIR = BASE_DIR / "wiki"

ENTITIES_CSV = OUT_DIR / "entities.csv"
RELATIONS_CSV = OUT_DIR / "relations.csv"

RISKS_DIR = WIKI_DIR / "risks"
CONTROLS_DIR = WIKI_DIR / "controls"
EVENTS_DIR = WIKI_DIR / "events"
HOME_MD = WIKI_DIR / "Home.md"

wikilink_count = 0


def read_csv(path: Path):
    if not path.exists():
        print(f"  [LOI] Khong tim thay file: {path}")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def na(value: str) -> str:
    """Tra ve gia tri hoac ghi chu 'Chua co du lieu.' neu rong."""
    v = (value or "").strip()
    return v if v else "Chua co du lieu."


def wikilink(entity_id: str, display_name: str) -> str:
    global wikilink_count
    wikilink_count += 1
    display = display_name.strip() if display_name and display_name.strip() else entity_id
    return f"[[{entity_id}|{display}]]"


def frontmatter(entity: dict) -> str:
    return (
        "---\n"
        f"id: {entity['id']}\n"
        f"type: {entity['type']}\n"
        f"verification_status: {entity.get('verification_status', '')}\n"
        f"data_origin: {entity.get('data_origin', '')}\n"
        "---\n\n"
    )


def build_risk_page(risk: dict, relations: list, entity_by_id: dict) -> str:
    lines = [frontmatter(risk)]
    lines.append(f"# {risk['name']}\n")
    lines.append(f"- **Category:** {na(risk.get('category'))}")
    lines.append(f"- **Mo ta:** {na(risk.get('description'))}")
    lines.append(f"- **Nguyen nhan (cause):** {na(risk.get('cause'))}")
    lines.append(f"- **Su kien (event, theo mo ta ho so goc):** {na(risk.get('event'))}")
    lines.append(f"- **Hau qua (impact):** {na(risk.get('impact'))}")
    lines.append(f"- **Muc rui ro co huu (inherent_level):** {na(risk.get('inherent_level'))}")
    lines.append(f"- **Muc rui ro con lai (residual_level):** {na(risk.get('residual_level'))}")
    owner_unit = risk.get("owner_unit_id", "").strip()
    if owner_unit:
        lines.append(f"- **Don vi so huu (owner_unit_id):** {owner_unit} "
                      f"_(chi la ma, chua co master data ten don vi - Chua co du lieu.)_")
    else:
        lines.append("- **Don vi so huu (owner_unit_id):** Chua co du lieu.")
    lines.append("")

    # Kiem soat lien quan: relations MITIGATES -> RiskId nay
    lines.append("## Kiem soat lien quan\n")
    mitigating = [r for r in relations
                  if r["relationship_type"] == "MITIGATES" and r["target_id"] == risk["id"]]
    if not mitigating:
        lines.append("Chua co du lieu.\n")
    else:
        for r in mitigating:
            ks = entity_by_id.get(r["source_id"])
            ks_name = ks["name"] if ks else r["source_id"]
            link = wikilink(r["source_id"], ks_name)
            lines.append(
                f"- {link} — relationship_type: `{r['relationship_type']}` "
                f"— evidence_quote: \"{r.get('evidence_quote', '')}\" "
                f"— verification_status: `{r.get('verification_status', '')}`"
            )
        lines.append("")

    # Su kien lien quan: relations OBSERVED_AS voi source_id == risk nay
    lines.append("## Su kien lien quan\n")
    observed = [r for r in relations
                if r["relationship_type"] == "OBSERVED_AS" and r["source_id"] == risk["id"]]
    if not observed:
        lines.append("Chua co du lieu.\n")
    else:
        for r in observed:
            sk = entity_by_id.get(r["target_id"])
            sk_name = sk["name"] if sk else r["target_id"]
            link = wikilink(r["target_id"], sk_name)
            lines.append(
                f"- {link} — relationship_type: `{r['relationship_type']}` "
                f"— evidence_quote: \"{r.get('evidence_quote', '')}\" "
                f"— verification_status: `{r.get('verification_status', '')}`"
            )
        lines.append("")

    return "\n".join(lines)


def build_control_page(control: dict, relations: list, entity_by_id: dict) -> str:
    lines = [frontmatter(control)]
    lines.append(f"# {control['name']}\n")
    lines.append(f"- **Loai kiem soat (control_type):** {na(control.get('control_type'))}")
    lines.append(f"- **Tan suat (frequency):** {na(control.get('frequency'))}")
    owner_role = control.get("owner_role_id", "").strip()
    if owner_role:
        lines.append(f"- **Vai tro phu trach (owner_role_id):** {owner_role} "
                      f"_(chi la ma, chua co master data ten vai tro - Chua co du lieu.)_")
    else:
        lines.append("- **Vai tro phu trach (owner_role_id):** Chua co du lieu.")
    lines.append(f"- **Hieu qua (effectiveness):** {na(control.get('effectiveness'))}")
    lines.append("")

    lines.append("## Rui ro duoc giam thieu (MITIGATES)\n")
    mitigates = [r for r in relations
                 if r["relationship_type"] == "MITIGATES" and r["source_id"] == control["id"]]
    if not mitigates:
        lines.append("Chua co du lieu.\n")
    else:
        for r in mitigates:
            rr = entity_by_id.get(r["target_id"])
            rr_name = rr["name"] if rr else r["target_id"]
            link = wikilink(r["target_id"], rr_name)
            lines.append(
                f"- {link} — relationship_type: `{r['relationship_type']}` "
                f"— evidence_quote: \"{r.get('evidence_quote', '')}\" "
                f"— verification_status: `{r.get('verification_status', '')}`"
            )
        lines.append("")

    return "\n".join(lines)


def build_event_page(event: dict, relations: list, entity_by_id: dict) -> str:
    lines = [frontmatter(event)]
    title = event.get("description") or event["id"]
    lines.append(f"# {title}\n")
    lines.append(f"- **Ngay xay ra (occurred_at):** {na(event.get('occurred_at'))}")
    lines.append(f"- **Ngay phat hien (discovered_at):** {na(event.get('discovered_at'))}")
    lines.append(f"- **Muc do nghiem trong (severity):** {na(event.get('severity'))}")
    lines.append(f"- **So tien ton that (loss_amount_vnd):** {na(event.get('loss_amount_vnd'))}")
    lines.append(f"- **Mo ta:** {na(event.get('description'))}")
    lines.append("")

    lines.append("## Rui ro tuong ung (OBSERVED_AS)\n")
    parents = [r for r in relations
               if r["relationship_type"] == "OBSERVED_AS" and r["target_id"] == event["id"]]
    if not parents:
        lines.append("Chua co du lieu.\n")
    else:
        for r in parents:
            rr = entity_by_id.get(r["source_id"])
            rr_name = rr["name"] if rr else r["source_id"]
            link = wikilink(r["source_id"], rr_name)
            lines.append(
                f"- {link} — relationship_type: `{r['relationship_type']}` "
                f"— evidence_quote: \"{r.get('evidence_quote', '')}\" "
                f"— verification_status: `{r.get('verification_status', '')}`"
            )
        lines.append("")

    return "\n".join(lines)


def build_home(risks, controls, events, relations) -> str:
    lines = ["# Wiki Risk Graph — Trang chu\n"]
    lines.append("## Thong ke\n")
    lines.append(f"- So node RuiRo: {len(risks)}")
    lines.append(f"- So node KiemSoat: {len(controls)}")
    lines.append(f"- So node SuKienRuiRo: {len(events)}")
    lines.append(f"- Tong so edge (relations): {len(relations)}")
    mitigates_n = sum(1 for r in relations if r["relationship_type"] == "MITIGATES")
    observed_n = sum(1 for r in relations if r["relationship_type"] == "OBSERVED_AS")
    lines.append(f"  - MITIGATES: {mitigates_n}")
    lines.append(f"  - OBSERVED_AS: {observed_n}")
    lines.append("")

    lines.append("## Danh sach Rui Ro\n")
    for r in risks:
        lines.append(f"- {wikilink(r['id'], r['name'])}")
    lines.append("")

    lines.append("## Danh sach Kiem Soat\n")
    for c in controls:
        lines.append(f"- {wikilink(c['id'], c['name'])}")
    lines.append("")

    lines.append("## Danh sach Su Kien Rui Ro\n")
    for e in events:
        lines.append(f"- {wikilink(e['id'], e['name'])}")
    lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 70)
    print("BUOC 3 - SINH WIKI MARKDOWN")
    print("=" * 70)

    entities = read_csv(ENTITIES_CSV)
    relations = read_csv(RELATIONS_CSV)

    if not entities:
        print("  [LOI] Khong co entities.csv. Hay chay build_entities.py truoc.")
        return 1

    entity_by_id = {e["id"]: e for e in entities}
    risks = [e for e in entities if e["type"] == "RuiRo"]
    controls = [e for e in entities if e["type"] == "KiemSoat"]
    events = [e for e in entities if e["type"] == "SuKienRuiRo"]

    for d in (RISKS_DIR, CONTROLS_DIR, EVENTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    pages_written = 0

    for r in risks:
        content = build_risk_page(r, relations, entity_by_id)
        (RISKS_DIR / f"{r['id']}.md").write_text(content, encoding="utf-8")
        pages_written += 1

    for c in controls:
        content = build_control_page(c, relations, entity_by_id)
        (CONTROLS_DIR / f"{c['id']}.md").write_text(content, encoding="utf-8")
        pages_written += 1

    for e in events:
        content = build_event_page(e, relations, entity_by_id)
        (EVENTS_DIR / f"{e['id']}.md").write_text(content, encoding="utf-8")
        pages_written += 1

    home_content = build_home(risks, controls, events, relations)
    HOME_MD.write_text(home_content, encoding="utf-8")
    pages_written += 1

    print(f"\nSo trang Wiki da tao: {pages_written}")
    print(f"  - RuiRo: {len(risks)} trang trong wiki/risks/")
    print(f"  - KiemSoat: {len(controls)} trang trong wiki/controls/")
    print(f"  - SuKienRuiRo: {len(events)} trang trong wiki/events/")
    print(f"  - Home.md: 1 trang")
    print(f"So wikilink da sinh (tinh ca Home.md): {wikilink_count}")

    # Vi du duong di KiemSoat -> RuiRo -> SuKienRuiRo
    print("\nVi du duong di KiemSoat -> RuiRo -> SuKienRuiRo:")
    example_shown = False
    for rel1 in relations:
        if rel1["relationship_type"] != "MITIGATES":
            continue
        risk_id = rel1["target_id"]
        for rel2 in relations:
            if rel2["relationship_type"] == "OBSERVED_AS" and rel2["source_id"] == risk_id:
                ks = entity_by_id.get(rel1["source_id"], {}).get("name", rel1["source_id"])
                rr = entity_by_id.get(risk_id, {}).get("name", risk_id)
                sk = entity_by_id.get(rel2["target_id"], {}).get("name", rel2["target_id"])
                print(f"  [{rel1['source_id']}] {ks}")
                print(f"    -> MITIGATES -> [{risk_id}] {rr}")
                print(f"       -> OBSERVED_AS -> [{rel2['target_id']}] {sk}")
                example_shown = True
                break
        if example_shown:
            break
    if not example_shown:
        print("  Khong tim thay duong di day du trong du lieu hien tai.")

    print("\nKET LUAN: Da sinh Wiki thanh cong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
