#!/usr/bin/env python3
"""
Sinh bo cau hoi danh gia: buoi_14/data/eval/questions.csv

NGUYEN TAC CHONG BIA GOLD
    Moi cau hoi duoc SINH RA TU mot chunk co that trong corpus, nen
    `expected_chunk_id` luon xac minh duoc: no chinh la chunk da dung de dat cau hoi.
    Khong co cau hoi nao duoc gan gold bang cam tinh.

    Chi chon nhung Dieu co TIEU DE DUY NHAT trong toan corpus. Neu tieu de trung
    (vi du "Pham vi dieu chinh" xuat hien o moi luat) thi cau hoi SEMANTIC se da
    nghia va gold khong con xac minh duoc -> loai bo.

Ba loai cau hoi:
    EXACT_KEYWORD - hoi thang bang so hieu van ban + so dieu (loi the cua BM25)
    SEMANTIC      - chi mo ta noi dung, KHONG chua so hieu/so dieu (loi the cua Dense)
    MIXED         - vua co so hieu vua dien dat theo noi dung
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import corpus  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

COLUMNS = ["question_id", "question", "expected_chunk_id", "query_type", "note"]

# Tieu de qua chung chung -> cau hoi semantic se da nghia, khong dung lam gold
GENERIC = {
    "phạm vi điều chỉnh", "đối tượng áp dụng", "giải thích từ ngữ", "hiệu lực thi hành",
    "tổ chức thực hiện", "điều khoản thi hành", "trách nhiệm thi hành", "quy định chung",
    "điều khoản chuyển tiếp", "giải thích thuật ngữ",
}
PER_TYPE = 8


def heading_of(rec: dict) -> str:
    first = rec["text"].split("\n", 1)[0].strip()
    m = re.match(r"^Điều\s+\d+[a-zA-ZÀ-ỹ]?\s*[\.\:]\s*(.+)$", first)
    return (m.group(1).strip() if m else "").rstrip(".:")


def main() -> int:
    records = list(corpus.load_chunks())

    # Chi lay Dieu tron ven (khong bi cat theo khoan) va du dai
    whole = [
        r for r in records
        if r["article"] and not r["clause"] and len(r["text"]) >= 300
    ]
    heads = {}
    for r in whole:
        h = heading_of(r)
        if not h or len(h) < 12 or len(h) > 110:
            continue
        if h.lower() in GENERIC:
            continue
        heads.setdefault(h.lower(), []).append((h, r))

    unique = [v[0] for v in heads.values() if len(v) == 1]
    # On dinh thu tu, uu tien trai deu cac van ban
    unique.sort(key=lambda hr: (hr[1]["document_id"], hr[1]["chunk_id"]))
    by_doc: dict[str, list] = {}
    for h, r in unique:
        by_doc.setdefault(r["document_id"], []).append((h, r))

    picked: list[tuple[str, dict]] = []
    round_i = 0
    while len(picked) < PER_TYPE * 3 and any(
        len(v) > round_i for v in by_doc.values()
    ):
        for doc in sorted(by_doc):
            if len(by_doc[doc]) > round_i:
                picked.append(by_doc[doc][round_i])
            if len(picked) >= PER_TYPE * 3:
                break
        round_i += 1

    rows = []
    qid = 0

    def add(q: str, rec: dict, qtype: str, note: str) -> None:
        nonlocal qid
        qid += 1
        rows.append(
            {
                "question_id": f"Q{qid:03d}",
                "question": q,
                "expected_chunk_id": rec["chunk_id"],
                "query_type": qtype,
                "note": note,
            }
        )

    exact = picked[0:PER_TYPE]
    semantic = picked[PER_TYPE:PER_TYPE * 2]
    mixed = picked[PER_TYPE * 2:PER_TYPE * 3]

    for h, r in exact:
        add(
            f"{r['so_ky_hieu']} Điều {r['article']} quy định nội dung gì?",
            r, "EXACT_KEYWORD",
            "Sinh tu so_ky_hieu + so dieu that cua chunk; gold = chinh chunk do",
        )
    for h, r in semantic:
        add(
            f"Quy định về {h[0].lower() + h[1:]} được nêu ở đâu?",
            r, "SEMANTIC",
            "Sinh tu tieu de Dieu (duy nhat trong corpus); KHONG chua so hieu/so dieu",
        )
    for h, r in mixed:
        add(
            f"Theo {r['so_ky_hieu']}, {h[0].lower() + h[1:]} được quy định thế nào?",
            r, "MIXED",
            "Vua co so hieu van ban vua dien dat theo noi dung tieu de Dieu",
        )

    config.QUESTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(config.QUESTIONS_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    index = corpus.chunk_index()
    bad = [r for r in rows if r["expected_chunk_id"] not in index]

    print("=" * 70)
    print("SINH BO CAU HOI DANH GIA")
    print("=" * 70)
    print(f"Ung vien Dieu co tieu de duy nhat: {len(unique)}")
    print(f"So cau hoi: {len(rows)}  ({dict(Counter(r['query_type'] for r in rows))})")
    print(f"So van ban duoc phu: {len({index[r['expected_chunk_id']]['document_id'] for r in rows})}/30")
    print(f"Gold khong ton tai trong corpus: {bad if bad else 'khong co (tat ca deu xac minh duoc)'}")
    print(f"Da ghi: {config.QUESTIONS_CSV.relative_to(config.BASE_DIR)}")
    print()
    for r in rows[:3]:
        print(f"  {r['question_id']} [{r['query_type']}] {r['question']}")
        print(f"        gold = {r['expected_chunk_id']}")
    return 0 if not bad and rows else 1


if __name__ == "__main__":
    sys.exit(main())
