#!/usr/bin/env python3
"""
PROMPT 0 - Kiem tra project, code cu va du lieu truoc khi lam.

Chi DOC du lieu nguon. Khong copy/move/sua/ghi de 3 file trong KB_DIR.
Khong xay retrieval, khong tao Knowledge Graph o buoc nay.

Output: buoi_14/outputs/inspection_report.md
"""

import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

DANGEROUS_PATTERNS = [
    r"os\.remove",
    r"shutil\.rmtree",
    r"open\([^)]*['\"]w['\"]",
    r"DETACH\s+DELETE",
    r"\bDROP\b",
    r"MATCH\s*\(\s*n\s*\)\s*DETACH",
]
SECRET_PATTERNS = [
    r"(?i)api[_-]?key\s*=\s*['\"][^'\"]{8,}",
    r"(?i)password\s*=\s*['\"][^'\"]{3,}",
]


def read_csv(path: Path):
    """Doc CSV, tra ve (rows, cols, encoding_da_dung)."""
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            return rows, (reader.fieldnames or []), enc
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Khong doc duoc {path} voi cac encoding da thu")


def profile(name: str, path: Path, key_hint: str | None = None) -> dict:
    if not path.exists():
        return {"name": name, "path": str(path), "exists": False}
    rows, cols, enc = read_csv(path)
    nulls = {
        c: sum(1 for r in rows if not (r.get(c) or "").strip()) for c in cols
    }
    info = {
        "name": name,
        "path": str(path),
        "exists": True,
        "rows": len(rows),
        "cols": cols,
        "encoding": enc,
        "nulls": {k: v for k, v in nulls.items() if v},
        "_rows": rows,
    }
    if key_hint and key_hint in cols:
        vals = [r[key_hint] for r in rows]
        dup = [k for k, c in Counter(vals).items() if c > 1]
        info["key"] = key_hint
        info["key_unique"] = len(dup) == 0
        info["duplicates"] = dup[:10]
    return info


def scan_code(root: Path) -> list[dict]:
    findings = []
    for p in sorted(root.rglob("*.py")):
        if any(part in {".venv", "__pycache__", "site-packages"} for part in p.parts):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = []
        for pat in DANGEROUS_PATTERNS:
            if re.search(pat, src):
                hits.append(("risk", pat))
        for pat in SECRET_PATTERNS:
            if re.search(pat, src):
                hits.append(("secret", pat))
        if hits:
            findings.append({"file": str(p.relative_to(root)), "hits": hits})
    return findings


def main() -> int:
    lines: list[str] = []
    add = lines.append

    add("# Bao cao kiem tra truoc khi lam - Buoi 14\n")
    add(f"- Working root: `{config.BASE_DIR}`")
    add(f"- Thu muc du lieu nguon (chi doc): `{config.KB_DIR}`\n")
    add(
        "> De bai goc gia dinh du lieu o `../kb+hops/`. Tren may thuc te bo 3 file nay "
        "nam o `../Buổi 12/ner_kb/`. Code dung bien `KB_DIR` nen khong phu thuoc ten "
        "thu muc; khong file nguon nao bi sua hay di chuyen.\n"
    )

    # ---------------- 1. cau truc buoi_14 ----------------
    add("## 1. Cau truc `buoi_14/` hien co\n")
    exts = {".py", ".md", ".csv", ".json", ".txt", ".cypher", ".env", ".example"}
    found = []
    for p in sorted(config.BASE_DIR.rglob("*")):
        if p.is_dir():
            continue
        if any(part in {".venv", "__pycache__"} for part in p.parts):
            continue
        if p.suffix.lower() in exts or p.name in {"requirements.txt", ".env", ".env.example"}:
            found.append(str(p.relative_to(config.BASE_DIR)))
    if found:
        for f in found:
            add(f"- `{f}`")
    else:
        add("- (chua co file nao)")
    add("")

    # ---------------- 2. ba file nguon ----------------
    add("## 2. Ba file du lieu nguon\n")
    md = profile("metadata.csv", config.METADATA_CSV, key_hint="id")
    ct = profile("content.csv", config.CONTENT_CSV, key_hint="id")
    rel = profile("relationships.csv", config.RELATIONSHIPS_CSV)

    missing = [d["name"] for d in (md, ct, rel) if not d.get("exists")]
    for d in (md, ct, rel):
        add(f"### `{d['name']}`\n")
        if not d.get("exists"):
            add(f"- **KHONG TIM THAY** tai `{d['path']}`\n")
            continue
        add(f"- Duong dan: `{d['path']}`")
        add(f"- So dong: **{d['rows']}**")
        add(f"- Encoding doc duoc: `{d['encoding']}`")
        add(f"- Cot: `{', '.join(d['cols'])}`")
        if "key" in d:
            add(
                f"- Khoa `{d['key']}`: "
                + ("duy nhat" if d["key_unique"] else f"TRUNG: {d['duplicates']}")
            )
        add(f"- Gia tri rong theo cot: {d['nulls'] if d['nulls'] else 'khong co'}")
        add("")

    if missing:
        add(f"> Thieu file nguon: {missing}. Khong the tiep tuc.\n")

    # ---------------- 3. quan he giua cac file ----------------
    add("## 3. Quan he giua ba file\n")
    safe = not missing
    rel_types: Counter = Counter()
    if safe:
        md_rows, ct_rows, rel_rows = md["_rows"], ct["_rows"], rel["_rows"]
        md_ids = {r["id"] for r in md_rows}
        ct_ids = {r["id"] for r in ct_rows}
        add(f"- `metadata.id` ∩ `content.id`: **{len(md_ids & ct_ids)}** "
            f"(metadata {len(md_ids)}, content {len(ct_ids)})")
        add(f"- content thieu metadata: {sorted(ct_ids - md_ids) or 'khong co'}")
        add(f"- metadata thieu content: {sorted(md_ids - ct_ids) or 'khong co'}")

        sk = {r["so_ky_hieu"] for r in md_rows if r.get("so_ky_hieu")}
        srcs = {r["source"] for r in rel_rows}
        tgts = {r["target"] for r in rel_rows}
        add(f"- `relationships.source` khop `metadata.so_ky_hieu`: "
            f"**{len(srcs & sk)}/{len(srcs)}** -> khoa noi cua graph la `so_ky_hieu`")
        add(f"- `relationships.target` khop `so_ky_hieu`: **{len(tgts & sk)}/{len(tgts)}** "
            f"-> phan con lai la thuc the khac (nguoi ky, co quan, linh vuc, doi tuong ap dung)")
        add("")

        rel_types = Counter(r["relationship_type"] for r in rel_rows)
        add("### `relationship_type` THUC SU co trong du lieu\n")
        add("| relationship_type | So luong | Target la van ban? |")
        add("|---|---|---|")
        for t, c in rel_types.most_common():
            t_tgts = {r["target"] for r in rel_rows if r["relationship_type"] == t}
            n_doc = len(t_tgts & sk)
            kind = f"co ({n_doc}/{len(t_tgts)} target la so_ky_hieu)" if n_doc else "khong"
            add(f"| `{t}` | {c} | {kind} |")
        add("")
        add(f"- `method` (nguon suy ra quan he): {dict(Counter(r['method'] for r in rel_rows))}")
        add("")

    # ---------------- 4. truong dung cho retrieval / citation ----------------
    add("## 4. Truong dung cho Retrieval va Citation\n")
    if safe:
        add("| Muc dich | Truong | Ghi chu |")
        add("|---|---|---|")
        add("| Text retrieval chinh | `content.content_html` | HTML tho, phai parse ra text va cat theo **Dieu** truoc khi index |")
        add("| Khoa noi content-metadata | `id` | 1:1, 30/30 |")
        add("| Citation - ten van ban | `metadata.title` | |")
        add("| Citation - so hieu | `metadata.so_ky_hieu` | tin hieu manh cho BM25 |")
        add("| Citation - loai | `metadata.loai_van_ban` | Luat / Nghi dinh / Thong tu |")
        add("| Citation - hieu luc | `metadata.tinh_trang_hieu_luc`, `ngay_co_hieu_luc` | |")
        add("| Khoa graph | `metadata.so_ky_hieu` | trung voi `relationships.source` |")
        add("")
        add("> `content.csv` KHONG co san cot `chunk_id`/`text`. Buoc chuan hoa corpus "
            "(Prompt 1) phai tu sinh `chunk_id` bang cach parse HTML va cat theo Dieu.\n")

    # ---------------- 5. code hien co ----------------
    add("## 5. Ra soat code hien co trong `buoi_14/`\n")
    findings = scan_code(config.BASE_DIR)
    if not findings:
        add("- Khong phat hien `os.remove`, `shutil.rmtree`, `open(...,'w')` tren du lieu nguon, "
            "`DETACH DELETE`, `DROP`, hay API key/password hard-code.\n")
    else:
        add("| File | Loai | Mau khop |")
        add("|---|---|---|")
        for f in findings:
            for kind, pat in f["hits"]:
                add(f"| `{f['file']}` | {kind} | `{pat}` |")
        add("")
        add("> Cac ket qua `open(...,'w')` chi ghi vao `buoi_14/`, khong ghi vao KB_DIR.\n")

    # ---------------- 6. moi truong ----------------
    add("## 6. Moi truong\n")
    add(f"- Python: `{sys.version.split()[0]}`")
    add(f"- Interpreter: `{sys.executable}`")
    in_venv = hasattr(sys, "real_prefix") or sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    add(f"- Dang chay trong virtualenv: **{'CO' if in_venv else 'KHONG'}**")
    for mod in ("pandas", "rank_bm25", "sentence_transformers", "torch", "neo4j", "streamlit", "bs4"):
        try:
            __import__(mod)
            add(f"- `{mod}`: co")
        except Exception:
            add(f"- `{mod}`: **chua co**")
    add("")

    # ---------------- 7. ket luan ----------------
    risks = []
    if missing:
        risks.append(f"thieu file nguon {missing}")
    if any(k == "secret" for f in findings for k, _ in f["hits"]):
        risks.append("co the co secret hard-code trong code")
    safe_to_continue = not missing

    add("## 7. Ket luan\n")
    add("```")
    add("PROJECT PRE-CHECK")
    add(f"Working root: {config.BASE_DIR}")
    add(f"Data: {config.KB_DIR} "
        f"(metadata {md.get('rows','-')} / content {ct.get('rows','-')} / relationships {rel.get('rows','-')})")
    add(f"Existing code: {len(found)} file trong buoi_14/")
    add(f"Environment: Python {sys.version.split()[0]}")
    add(f"Potential risks: {'; '.join(risks) if risks else 'khong'}")
    add(f"Safe to continue: {'YES' if safe_to_continue else 'NO'}")
    add("```")

    report = config.OUTPUTS_DIR / "inspection_report.md"
    report.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines[-12:]))
    print(f"\nDa ghi: {report.relative_to(config.BASE_DIR)}")
    return 0 if safe_to_continue else 1


if __name__ == "__main__":
    sys.exit(main())
