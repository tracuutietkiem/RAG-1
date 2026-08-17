#!/usr/bin/env python3
"""
PROMPT 1 - Chuan hoa corpus cho Retrieval va Citation.

Doc (chi doc):
    KB_DIR/metadata.csv       -> metadata / citation
    KB_DIR/content.csv        -> content_html, nguon text retrieval chinh
    KB_DIR/relationships.csv  -> chi de doi chieu so_ky_hieu (khong dung o buoc nay)

Ghi:
    buoi_14/data/processed/chunks_normalized.csv

Cach cat chunk:
    HTML -> text -> cat theo "Dieu N." (don vi nghiep vu tu nhien cua van ban phap luat).
    Dieu qua dai (> MAX_CHUNK_CHARS) duoc cat tiep theo khoan "1." "2." ...
    Phan dau van ban (truoc Dieu 1) giu lam mot chunk rieng vi chua so hieu,
    co quan ban hanh, can cu phap ly - deu la thong tin citation that.

Khong bia metadata. Khong xoa so hieu van ban / so dieu khi chuan hoa text.
"""

import argparse
import csv
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

OUT_COLUMNS = [
    "chunk_id",
    "document_id",
    "text",
    "index_text",
    "source_file",
    "title",
    "so_ky_hieu",
    "document_type",
    "chapter",
    "section",
    "article",
    "clause",
    "effective_date",
    "status",
    "issuing_body",
    "signer",
    "field",
    "citation",
]

# "Dieu 12." / "Dieu 12:" / "Dieu 12a." o dau dong
RE_ARTICLE = re.compile(r"^\s*Điều\s+(\d+[a-zA-ZÀ-ỹ]?)\s*[\.\:]\s*(.*)$")
RE_CHAPTER = re.compile(r"^\s*(Chương\s+[IVXLCDM\d]+[\.\:]?\s*.*)$", re.IGNORECASE)
RE_SECTION = re.compile(r"^\s*(Mục\s+[IVXLCDM\d]+[\.\:]?\s*.*)$", re.IGNORECASE)
# Khoan "1." "2." o dau dong
RE_CLAUSE = re.compile(r"^\s*(\d{1,2})\s*\.\s+(?=\S)")


def read_csv(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Khong doc duoc {path}")


def html_to_text(raw: str) -> str:
    """HTML -> text thuan, giu xuong dong theo block."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover
        print("[LOI] Thieu beautifulsoup4. Chay: pip install beautifulsoup4 lxml")
        raise
    try:
        soup = BeautifulSoup(raw, "lxml")
    except Exception:
        soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    return text


def normalize_text(text: str) -> str:
    """
    Chuan hoa nhe nhang:
      - NFC (tieng Viet co dau on dinh);
      - bo ky tu dieu khien / zero-width;
      - gom khoang trang thua;
      - gom dong trong.
    KHONG stemming, KHONG bo so hieu van ban, KHONG bo so dieu.
    """
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ").replace("​", "").replace("﻿", "")
    text = re.sub(r"[\r\f\v]", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_articles(text: str) -> list[dict]:
    """Cat text thanh cac block theo 'Dieu N.', kem chuong/muc dang hieu luc."""
    blocks: list[dict] = []
    chapter = ""
    section = ""
    current: dict | None = None
    preamble: list[str] = []

    for line in text.split("\n"):
        m_ch = RE_CHAPTER.match(line)
        if m_ch and len(line) < 200:
            chapter = m_ch.group(1).strip()
            if current is not None:
                current["lines"].append(line)
            else:
                preamble.append(line)
            continue

        m_sec = RE_SECTION.match(line)
        if m_sec and len(line) < 200:
            section = m_sec.group(1).strip()
            if current is not None:
                current["lines"].append(line)
            else:
                preamble.append(line)
            continue

        m_art = RE_ARTICLE.match(line)
        if m_art:
            if current is not None:
                blocks.append(current)
            current = {
                "article": m_art.group(1),
                "heading": m_art.group(2).strip(),
                "chapter": chapter,
                "section": section,
                "lines": [line.strip()],
            }
            continue

        if current is None:
            preamble.append(line)
        else:
            current["lines"].append(line)

    if current is not None:
        blocks.append(current)

    result: list[dict] = []
    pre = normalize_text("\n".join(preamble))
    if len(pre) >= config.MIN_CHUNK_CHARS:
        result.append(
            {"article": "", "heading": "Phần mở đầu", "chapter": "", "section": "",
             "text": pre}
        )
    for b in blocks:
        result.append(
            {"article": b["article"], "heading": b["heading"], "chapter": b["chapter"],
             "section": b["section"], "text": normalize_text("\n".join(b["lines"]))}
        )
    return result


def dedupe_articles(blocks: list[dict]) -> tuple[list[dict], int]:
    """
    Van ban thuong co muc luc lap lai 'Dieu N' voi noi dung rat ngan.
    Giu ban co text dai nhat cho moi so dieu; dem so ban bi bo.
    """
    best: dict[str, dict] = {}
    order: list[str] = []
    dropped = 0
    for b in blocks:
        key = b["article"] or f"__preamble__{len(order)}"
        if key not in best:
            best[key] = b
            order.append(key)
        else:
            if len(b["text"]) > len(best[key]["text"]):
                best[key] = b
            dropped += 1
    return [best[k] for k in order], dropped


def _hard_split(block: dict, header: str, body: str, clause: str) -> list[dict]:
    """Cat cung theo do dai khi khong con moc nghiep vu nao de cat."""
    step = config.MAX_CHUNK_CHARS
    if len(body) <= step:
        return [dict(block, text=f"{header}\n{body}".strip(), clause=clause)]
    out = []
    n = 0
    for i in range(0, len(body), step):
        n += 1
        suffix = f"{clause}p{n}" if clause else f"p{n}"
        out.append(dict(block, text=f"{header}\n{body[i:i + step]}".strip(), clause=suffix))
    return out


def split_long_block(block: dict) -> list[dict]:
    """Cat block qua dai theo khoan '1.' '2.' ..., giu nguyen tieu de Dieu."""
    text = block["text"]
    if len(text) <= config.MAX_CHUNK_CHARS:
        return [dict(block, clause="")]

    lines = text.split("\n")
    header = lines[0] if lines else ""
    parts: list[tuple[str, list[str]]] = []
    cur_no = ""
    cur: list[str] = []
    for line in lines[1:]:
        m = RE_CLAUSE.match(line)
        if m:
            if cur:
                parts.append((cur_no, cur))
            cur_no = m.group(1)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        parts.append((cur_no, cur))

    if len(parts) <= 1:
        # Khong tach duoc theo khoan -> cat cung theo do dai, khong lam mat chu
        return _hard_split(block, header, "\n".join(lines[1:]), "")

    out: list[dict] = []
    for no, chunk_lines in parts:
        body = "\n".join(chunk_lines).strip()
        if len(body) < config.MIN_CHUNK_CHARS:
            continue
        # Mot khoan van co the rat dai -> ep tran do dai lan cuoi
        out.extend(_hard_split(block, header, body, no))
    return out or [dict(block, clause="")]


def build_citation(meta: dict, article: str, clause: str, chunk_id: str) -> str:
    """Citation chi dung metadata THAT. Khong bia."""
    parts = []
    title = (meta.get("title") or "").strip()
    sk = (meta.get("so_ky_hieu") or "").strip()
    parts.append(title if title else (sk or meta.get("id", "")))
    if sk and sk not in (title or ""):
        parts.append(sk)
    if article:
        parts.append(f"Điều {article}" + (f" khoản {clause}" if clause and clause.isdigit() else ""))
    parts.append(chunk_id)
    return " | ".join(p for p in parts if p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="chi xu ly N van ban dau (debug)")
    args = ap.parse_args()

    if not config.CONTENT_CSV.exists():
        print(f"[LOI] Khong tim thay {config.CONTENT_CSV}")
        return 1

    meta_rows = read_csv(config.METADATA_CSV)
    meta_by_id = {r["id"]: r for r in meta_rows}
    content_rows = read_csv(config.CONTENT_CSV)
    if args.limit:
        content_rows = content_rows[: args.limit]

    records: list[dict] = []
    total_dropped_toc = 0
    docs_no_article = []

    for row in content_rows:
        doc_id = row["id"]
        meta = meta_by_id.get(doc_id, {})
        raw = row.get("content_html") or ""
        text = normalize_text(html_to_text(raw))
        blocks = split_articles(text)
        blocks, dropped = dedupe_articles(blocks)
        total_dropped_toc += dropped
        if not any(b["article"] for b in blocks):
            docs_no_article.append(doc_id)

        seq = 0
        for b in blocks:
            for piece in split_long_block(b):
                body = piece["text"].strip()
                if len(body) < config.MIN_CHUNK_CHARS:
                    continue
                seq += 1
                art = piece["article"]
                cl = piece.get("clause", "")
                suffix = f"D{art}" if art else "MD"
                if cl:
                    suffix += f"K{cl}"
                chunk_id = f"{doc_id}_{suffix}_{seq:03d}"
                # index_text = header dinh danh van ban + noi dung.
                # Ly do: mot chunk "Dieu N" KHONG chua so hieu van ban cua chinh no,
                # nen retrieval khong the noi cau hoi "73/2016/ND-CP Dieu 100" voi dung
                # dieu do; ket qua la trang bia (chua so hieu lap lai nhieu lan) luon
                # thang. Header chi gom metadata CO THAT (so_ky_hieu, loai, title),
                # khong bia them, va CHI dung de index - `text` hien thi giu nguyen.
                header_bits = [
                    meta.get("so_ky_hieu", ""),
                    meta.get("loai_van_ban", ""),
                    meta.get("title", ""),
                ]
                if art:
                    header_bits.append(f"Điều {art}")
                header = " ".join(b for b in header_bits if b).strip()

                records.append(
                    {
                        "chunk_id": chunk_id,
                        "document_id": doc_id,
                        "text": body,
                        "index_text": f"{header}\n{body}" if header else body,
                        "source_file": "content.csv",
                        "title": meta.get("title", ""),
                        "so_ky_hieu": meta.get("so_ky_hieu", ""),
                        "document_type": meta.get("loai_van_ban", ""),
                        "chapter": piece.get("chapter", ""),
                        "section": piece.get("section", ""),
                        "article": art,
                        "clause": cl,
                        "effective_date": meta.get("ngay_co_hieu_luc", ""),
                        "status": meta.get("tinh_trang_hieu_luc", ""),
                        "issuing_body": meta.get("co_quan_ban_hanh", ""),
                        "signer": meta.get("nguoi_ky", ""),
                        "field": meta.get("linh_vuc", ""),
                        "citation": build_citation(meta, art, cl, chunk_id),
                    }
                )

    # ---------------- kiem tra ----------------
    ids = [r["chunk_id"] for r in records]
    dup = [i for i in set(ids) if ids.count(i) > 1] if len(set(ids)) != len(ids) else []
    empty_text = sum(1 for r in records if not r["text"].strip())

    config.CHUNKS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(config.CHUNKS_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(records)

    print("=" * 70)
    print("PROMPT 1 - CHUAN HOA CORPUS")
    print("=" * 70)
    print(f"Nguon (chi doc) : {config.KB_DIR}")
    print(f"Output          : {config.CHUNKS_CSV.relative_to(config.BASE_DIR)}")
    print()
    print(f"Tong so chunk           : {len(records)}")
    print(f"So document             : {len({r['document_id'] for r in records})}")
    print(f"Chunk thieu text        : {empty_text}")
    print(f"chunk_id trung          : {dup if dup else 'khong co'}")
    print(f"Ban muc luc bi loai bo  : {total_dropped_toc}")
    print(f"Van ban khong tach duoc Dieu: {docs_no_article if docs_no_article else 'khong co'}")
    print(f"Do dai text: min={min(len(r['text']) for r in records)}, "
          f"trung binh={sum(len(r['text']) for r in records) // len(records)}, "
          f"max={max(len(r['text']) for r in records)}")
    print()
    print("--- 3 SAMPLE RECORD ---")
    for r in records[:3]:
        print(f"  chunk_id : {r['chunk_id']}")
        print(f"  citation : {r['citation']}")
        print(f"  text     : {r['text'][:160].replace(chr(10), ' / ')}...")
        print()

    ok = not dup and not empty_text and records
    print(f"KET LUAN: {'DAT' if ok else 'CHUA DAT'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
