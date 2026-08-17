#!/usr/bin/env python3
"""
BUOI 15 - PROMPT 2: Nap du lieu bao mat (allowed_roles) vao Neo4j (Secure Graph Loading).

    python scripts/load_secure_kg.py
    python scripts/load_secure_kg.py --dry-run     # chi doc + tinh toan, khong cham Neo4j
    python scripts/load_secure_kg.py --verify-only # chi chay lai 2 truy van kiem tra

Doc  : buoi_14/data/processed/chunks_secure.csv  (cot allowed_roles, JSON list)
Ghi  : thuoc tinh `allowed_roles` (List<String>) len node (:DieuKhoan) va (:VanBan)
       da co san trong Neo4j tu Buoi 14 (`scripts/load_mini_kg.py`).

AN TOAN:
    - KHONG BAO GIO chay MATCH (n) DETACH DELETE n.
    - Chi MERGE theo id co san (id = chunk_id cho DieuKhoan, id = so_ky_hieu cho
      VanBan) -> chay lai nhieu lan KHONG tao node trung, CHI ghi de/cap nhat
      thuoc tinh allowed_roles.
    - Neu node chua ton tai (vi du hoc vien chua chay load_mini_kg.py cua Buoi 14),
      script van tao moi de khong mat du lieu, nhung danh dau rieng
      `lab_session = "buoi_15"` (khac voi node goc cua Buoi 14 la "buoi_14") de
      phan biet nguon goc, dung theo dung yeu cau de bai.
    - Node/quan he da co tu Buoi 14 giu nguyen `lab_session = "buoi_14"`; script
      nay CHI bo sung them 2 thuoc tinh moi (`allowed_roles`, `rbac_tagged_at`,
      `rbac_lab_session = "buoi_15"`) len node co san, KHONG doi lab_session goc.

Neu Neo4j chua chay (vi du dang chay tren May cua hoc vien, khong phai moi
truong dang thuc thi script): ghi bao cao "NOT RUN" + ly do ro rang, KHONG lam
crash toan bo pipeline (giong trieu ly load_mini_kg.py cua Buoi 14).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

REPORT_PATH = config.OUTPUTS_DIR / "rbac_kg_load_report.md"


def _log_error(exc: BaseException, context: str) -> Path:
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = config.OUTPUTS_DIR / f"error_load_secure_kg_{ts}.txt"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().isoformat()}] Loi trong: {context}\n")
        fh.write(f"{type(exc).__name__}: {exc}\n\n")
        fh.write(traceback.format_exc())
    return log_path


def read_secure_chunks() -> list[dict]:
    path = config.CHUNKS_SECURE_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"Khong thay {path}. Chay truoc: python scripts/assign_security_tags.py"
        )
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise RuntimeError(f"{path} rong.")
    for r in rows:
        raw = r.get("allowed_roles", "")
        try:
            roles = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            roles = [x.strip() for x in raw.split(",") if x.strip()]
        try:
            config.validate_roles(roles)
        except ValueError as exc:
            raise ValueError(f"chunk_id={r.get('chunk_id')}: {exc}") from exc
        if not roles:
            raise ValueError(
                f"chunk_id={r.get('chunk_id')} co allowed_roles rong - "
                "chay lai scripts/assign_security_tags.py truoc."
            )
        r["_roles"] = roles
    return rows


def build_update_model(rows: list[dict]) -> dict:
    """DieuKhoan lay allowed_roles truc tiep tu CSV. VanBan (van ban cha) lay
    UNION cac allowed_roles cua moi DieuKhoan thuoc no - vi mot van ban co the
    chua nhieu Dieu voi muc do nhay cam khac nhau, VanBan-level phai la tap RONG
    NHAT de khong chan nham nguoi dung con quyen xem it nhat mot Dieu ben trong."""
    dieukhoan_updates = []
    vanban_roles: dict[str, set[str]] = defaultdict(set)

    for r in rows:
        chunk_id = r["chunk_id"]
        so_ky_hieu = r.get("so_ky_hieu") or r.get("document_id", "")
        roles = r["_roles"]
        dieukhoan_updates.append({
            "id": chunk_id,
            "document_id": r.get("document_id", ""),
            "so_ky_hieu": so_ky_hieu,
            "allowed_roles": roles,
        })
        vanban_roles[so_ky_hieu].update(roles)

    vanban_updates = [
        {"id": sk, "so_ky_hieu": sk, "allowed_roles": sorted(roles)}
        for sk, roles in vanban_roles.items()
    ]
    return {"dieukhoan": dieukhoan_updates, "vanban": vanban_updates}


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


def load_into_neo4j(model: dict) -> dict:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )
    driver.verify_connectivity()
    stats: dict = {}
    try:
        with driver.session(database=config.NEO4J_DATABASE) as s:
            # ---- VanBan: MERGE theo id co san (so_ky_hieu). Neu chua ton tai
            # (hoc vien chua chay Buoi 14), tao moi voi lab_session='buoi_15'
            # de phan biet nguon goc; node cu tu Buoi 14 GIU NGUYEN lab_session.
            r = s.run(
                """
                UNWIND $rows AS row
                MERGE (v:VanBan {id: row.id})
                ON CREATE SET v.lab_session = 'buoi_15', v.so_ky_hieu = row.so_ky_hieu
                SET v.allowed_roles = row.allowed_roles,
                    v.rbac_lab_session = 'buoi_15',
                    v.rbac_tagged_at = datetime()
                RETURN count(*) AS n
                """,
                rows=model["vanban"],
            ).single()
            stats["VanBan_cap_nhat"] = r["n"]

            total = 0
            rows = model["dieukhoan"]
            for i in range(0, len(rows), 500):
                r = s.run(
                    """
                    UNWIND $rows AS row
                    MERGE (d:DieuKhoan {id: row.id})
                    ON CREATE SET d.lab_session = 'buoi_15',
                                  d.document_id = row.document_id,
                                  d.so_ky_hieu = row.so_ky_hieu
                    SET d.allowed_roles = row.allowed_roles,
                        d.rbac_lab_session = 'buoi_15',
                        d.rbac_tagged_at = datetime()
                    RETURN count(*) AS n
                    """,
                    rows=rows[i:i + 500],
                ).single()
                total += r["n"]
            stats["DieuKhoan_cap_nhat"] = total

            # ---- kiem tra sau khi nap ----
            n_dk_with_roles = s.run(
                "MATCH (d:DieuKhoan) WHERE d.allowed_roles IS NOT NULL "
                "RETURN count(d) AS n"
            ).single()["n"]
            n_vb_with_roles = s.run(
                "MATCH (v:VanBan) WHERE v.allowed_roles IS NOT NULL "
                "RETURN count(v) AS n"
            ).single()["n"]
            n_dk_total = s.run("MATCH (d:DieuKhoan) RETURN count(d) AS n").single()["n"]
            n_vb_total = s.run("MATCH (v:VanBan) RETURN count(v) AS n").single()["n"]

            sample = s.run(
                """
                MATCH (v:VanBan) WHERE v.allowed_roles IS NOT NULL
                WITH v LIMIT 1
                OPTIONAL MATCH (v)-[:CONTAINS]->(d:DieuKhoan)
                RETURN v.id AS van_ban_id, v.so_ky_hieu AS so_ky_hieu,
                       v.allowed_roles AS van_ban_roles,
                       collect({id: d.id, allowed_roles: d.allowed_roles})[0..5] AS dieu_khoan_sample
                """
            ).single()

        driver.close()
        return {
            "written": stats,
            "n_dieukhoan_with_roles": n_dk_with_roles,
            "n_dieukhoan_total": n_dk_total,
            "n_vanban_with_roles": n_vb_with_roles,
            "n_vanban_total": n_vb_total,
            "sample": dict(sample) if sample else None,
        }
    except Exception:
        driver.close()
        raise


def write_report(model: dict, ran: bool, reason: str, result: dict | None) -> Path:
    L: list[str] = []
    add = L.append
    add("# Bao cao nap thuoc tinh RBAC (allowed_roles) vao Neo4j - Buoi 15\n")
    add(f"- Nguon: `data/processed/chunks_secure.csv`")
    add(f"- Cap nhat node: `(:VanBan)` va `(:DieuKhoan)` da nap tu Buoi 14")
    add(f"- Thuoc tinh moi: `allowed_roles` (List<String>), `rbac_lab_session = \"buoi_15\"`, "
        f"`rbac_tagged_at`\n")

    add("## 1. Mo hinh cap nhat (truoc khi cham Neo4j)\n")
    add(f"- So node `VanBan` se cap nhat: **{len(model['vanban'])}**")
    add(f"- So node `DieuKhoan` se cap nhat: **{len(model['dieukhoan'])}**\n")

    add("## 2. Ket qua nap\n")
    if not ran:
        add("```\nNOT RUN\n```")
        add(f"**Ly do:** {reason}\n")
        add("Cach chay lai khi Neo4j (Neo4j Desktop / server cuc bo) da san sang:\n")
        add("```bash")
        add("# .env cuc bo (buoi_14/.env) da co NEO4J_URI/USER/PASSWORD/DATABASE tu Buoi 14")
        add("pip install neo4j")
        add("python scripts/load_secure_kg.py")
        add("```")
        add("\n> Luu y: neu ban dang chay Neo4j Desktop TREN CHINH MAY DANG THUC THI SCRIPT NAY, "
            "script se ket noi duoc qua `bolt://127.0.0.1:7687`. Neu script duoc chay tu moi truong "
            "khac (vi du moi truong dam may/cloud sandbox), `127.0.0.1` se KHONG tro toi Neo4j "
            "tren may cua ban - day la ly do pho bien nhat gay NOT RUN.\n")
    else:
        add("```\nRUN OK\n```")
        add("### Da ghi/cap nhat (MERGE, chay lai khong tao trung)\n")
        add("| Doi tuong | So node cap nhat |")
        add("|---|---|")
        for k, v in result["written"].items():
            add(f"| {k} | {v} |")
        add("")
        add("### Kiem tra sau khi nap\n")
        add(f"- Node `DieuKhoan` co `allowed_roles`: "
            f"**{result['n_dieukhoan_with_roles']}/{result['n_dieukhoan_total']}**")
        add(f"- Node `VanBan` co `allowed_roles`: "
            f"**{result['n_vanban_with_roles']}/{result['n_vanban_total']}**\n")
        add("### Mau kiem chung (1 VanBan + toi da 5 DieuKhoan lien ket)\n")
        s = result.get("sample")
        if s:
            add(f"- `VanBan.id` = `{s.get('van_ban_id')}` "
                f"(`so_ky_hieu={s.get('so_ky_hieu')}`)")
            add(f"- `VanBan.allowed_roles` = `{s.get('van_ban_roles')}`")
            add("- `DieuKhoan` mau:")
            for dk in s.get("dieu_khoan_sample") or []:
                add(f"  - `{dk.get('id')}` -> `allowed_roles = {dk.get('allowed_roles')}`")
        else:
            add("- Khong lay duoc mau (co the database rong).")
        add("")

    add("## 3. An toan du lieu\n")
    add("- Khong chay `MATCH (n) DETACH DELETE n` trong bat ky truong hop nao.")
    add("- Chi dung `MERGE` theo `id` co san -> chay lai nhieu lan KHONG tao node trung, "
        "chi ghi de thuoc tinh `allowed_roles`.")
    add("- Node moi tao (neu Buoi 14 chua nap) duoc danh dau rieng "
        "`lab_session = \"buoi_15\"` de phan biet voi node goc cua Buoi 14.")

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    return REPORT_PATH


def run(dry_run: bool, verify_only: bool) -> int:
    rows = read_secure_chunks()
    model = build_update_model(rows)
    print(f"VanBan se cap nhat   : {len(model['vanban'])}")
    print(f"DieuKhoan se cap nhat: {len(model['dieukhoan'])}")

    if dry_run:
        path = write_report(model, False, "Chay voi --dry-run, khong ket noi Neo4j", None)
        print(f"\nDa ghi: {path.relative_to(config.BASE_DIR)}")
        return 0

    ready, reason = neo4j_ready()
    result = None
    if ready:
        try:
            if verify_only:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(
                    config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
                )
                driver.verify_connectivity()
                with driver.session(database=config.NEO4J_DATABASE) as s:
                    n_dk = s.run(
                        "MATCH (d:DieuKhoan) WHERE d.allowed_roles IS NOT NULL "
                        "RETURN count(d) AS n"
                    ).single()["n"]
                    n_vb = s.run(
                        "MATCH (v:VanBan) WHERE v.allowed_roles IS NOT NULL "
                        "RETURN count(v) AS n"
                    ).single()["n"]
                driver.close()
                print(f"[VERIFY] DieuKhoan co allowed_roles: {n_dk}")
                print(f"[VERIFY] VanBan co allowed_roles   : {n_vb}")
                return 0
            result = load_into_neo4j(model)
            print("\nDa cap nhat vao Neo4j:")
            for k, v in result["written"].items():
                print(f"  {k:<24} {v}")
            print(f"  Kiem tra: DieuKhoan co allowed_roles = "
                  f"{result['n_dieukhoan_with_roles']}/{result['n_dieukhoan_total']}")
            print(f"  Kiem tra: VanBan co allowed_roles    = "
                  f"{result['n_vanban_with_roles']}/{result['n_vanban_total']}")
        except Exception as exc:  # noqa: BLE001
            ready = False
            reason = f"Khong ket noi/nap duoc Neo4j: {type(exc).__name__}: {str(exc)[:250]}"
            print(f"[LOI] {reason}")

    if not ready:
        print("=" * 74)
        print("NEO4J CHUA SAN SANG - rbac_kg_load_report.md se ghi NOT RUN")
        print("=" * 74)
        print(f"  Ly do: {reason}")

    path = write_report(model, ready and result is not None, reason, result)
    print(f"\nDa ghi: {path.relative_to(config.BASE_DIR)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                     help="chi dung mo hinh cap nhat, khong cham Neo4j")
    ap.add_argument("--verify-only", action="store_true",
                     help="chi chay lai 2 truy van dem, khong ghi gi them")
    args = ap.parse_args()
    return run(dry_run=args.dry_run, verify_only=args.verify_only)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        log_path = _log_error(exc, context="scripts/load_secure_kg.py")
        print(f"\n[LOI] {type(exc).__name__}: {exc}")
        print(f"[LOI] Da ghi log chi tiet vao: {log_path}")
        sys.exit(1)
