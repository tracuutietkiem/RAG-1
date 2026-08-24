"""
BUOI 18 - PROMPT 1: Cataloging & chuan bi du lieu cho UC3 & UC4.

Doc agribank_internal_policies.csv + chunks_combined_secure.csv (READ-ONLY,
tai su dung tu buoi_17/, khong sua). Thong ke van ban noi bo, phan loai theo
Domain (suy ra TU CHINH tieu de/noi dung van ban that - khong bia), kiem tra
day du 14 truong metadata.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

INTERNAL_CSV = BASE_DIR / os.environ["SOURCE_INTERNAL_POLICY_CSV"]
COMBINED_CSV = BASE_DIR / os.environ["SOURCE_COMBINED_SECURE_CSV"]

# Domain duoc suy ra TU TIEU DE THAT cua tung van ban noi bo (document_id -> domain).
# Day la anh xa co dinh, minh bach, doc duoc tu chinh cot 'title'/'so_ky_hieu' that
# trong du lieu - khong phai AI tu doan/bia. Moi domain gan voi tu khoa tra cuu de
# dung chung cho UC3 (tim van ban ben ngoai cung domain) va UC4 (loc theo Domain).
DOMAIN_MAP = {
    "agr_at01": {
        "domain": "An toàn kho quỹ & Vận chuyển tiền",
        "code": "KHO",
        "keywords": ["kho tiền", "vận chuyển tiền", "bảo vệ kho", "chìa khóa kho", "áp tải", "kiểm đếm"],
    },
    "agr_car02": {
        "domain": "Quản lý CAR & Rủi ro tín dụng",
        "code": "CAR",
        "keywords": ["an toàn vốn", "car", "hệ số rủi ro", "vốn tự có", "quỹ an toàn hệ thống"],
    },
    "agr_td03": {
        "domain": "Tín dụng & Phân cấp phán quyết",
        "code": "TD",
        "keywords": ["phán quyết", "hạn mức duyệt vay", "phân cấp", "ủy quyền", "kiểm tra sử dụng vốn vay", "cho vay"],
    },
    "agr_fx04": {
        "domain": "Ngoại tệ & Kinh doanh ngoại hối",
        "code": "NT",
        "keywords": ["ngoại tệ", "trạng thái ngoại tệ", "giao dịch ngoại hối", "tỷ giá"],
    },
    "agr_gp05": {
        "domain": "Mạng lưới & Mở rộng chi nhánh",
        "code": "ML",
        "keywords": ["mạng lưới", "chi nhánh", "phòng giao dịch", "mở rộng"],
    },
    "agr_bh06": {
        "domain": "Bảo hiểm rủi ro nghiệp vụ",
        "code": "BH",
        "keywords": ["bảo hiểm", "rủi ro nghiệp vụ", "tài sản"],
    },
    "agr_it07": {
        "domain": "Bảo mật CNTT & AI",
        "code": "IT",
        "keywords": ["an toàn thông tin", "cntt", "dữ liệu", "mã hóa", "ai", "hệ thống thông tin"],
    },
    "agr_hr08": {
        "domain": "Nhân sự & Quy hoạch cán bộ",
        "code": "NS",
        "keywords": ["nhân sự", "quy hoạch", "bổ nhiệm", "miễn nhiệm", "cán bộ quản lý"],
    },
    "agr_tc09": {
        "domain": "Tài chính & Mua sắm nội bộ",
        "code": "TC",
        "keywords": ["chi tiêu", "mua sắm", "tài sản nội bộ", "tài chính"],
    },
    "agr_xln10": {
        "domain": "Phân loại nợ & Xử lý nợ xấu",
        "code": "XLN",
        "keywords": ["phân loại nợ", "nợ xấu", "trích lập dự phòng", "xử lý nợ"],
    },
}

REQUIRED_14_COLS = [
    "chunk_id", "document_id", "text", "source_file", "title", "so_ky_hieu",
    "loai_van_ban", "co_quan_ban_hanh", "ngay_ban_hanh", "chapter", "section",
    "article", "citation", "allowed_roles",
]


def main() -> None:
    df = pd.read_csv(INTERNAL_CSV)
    combined = pd.read_csv(COMBINED_CSV)

    lines = ["# Buổi 18 — Data Catalog Report (PROMPT 1)\n"]

    # 1. Thong ke van ban noi bo
    lines.append("## 1. Danh mục văn bản nội bộ Agribank\n")
    lines.append("| document_id | Số ký hiệu | Loại văn bản | Cơ quan ban hành | Ngày ban hành | Domain | Số chunk |")
    lines.append("|---|---|---|---|---|---|---|")
    docs = df.drop_duplicates("document_id")
    for _, r in docs.iterrows():
        doc_id = r["document_id"]
        n_chunks = int((df["document_id"] == doc_id).sum())
        domain = DOMAIN_MAP.get(doc_id, {}).get("domain", "CHƯA PHÂN LOẠI")
        lines.append(
            f"| {doc_id} | {r['so_ky_hieu']} | {r['loai_van_ban']} | {r['co_quan_ban_hanh']} | "
            f"{r['ngay_ban_hanh']} | {domain} | {n_chunks} |"
        )
    lines.append("")

    n_docs = docs["document_id"].nunique()
    n_domains = len(set(DOMAIN_MAP.get(d, {}).get("domain") for d in docs["document_id"] if d in DOMAIN_MAP))
    unmapped = [d for d in docs["document_id"] if d not in DOMAIN_MAP]

    lines.append(f"Tổng số văn bản nội bộ: **{n_docs}**  \nTổng số chunk nội bộ: **{len(df)}**\n")
    if unmapped:
        lines.append(f"⚠️ Văn bản CHƯA có domain map (cần bổ sung thủ công): {unmapped}\n")

    # 2. Phan loai theo domain (dem so chunk)
    lines.append("## 2. Phân bố chunk nội bộ theo Domain\n")
    lines.append("| Domain | Số văn bản | Số chunk |")
    lines.append("|---|---|---|")
    domain_docs: dict[str, list[str]] = {}
    for doc_id, meta in DOMAIN_MAP.items():
        domain_docs.setdefault(meta["domain"], []).append(doc_id)
    for domain, doc_ids in domain_docs.items():
        n_chunk = int(df["document_id"].isin(doc_ids).sum())
        lines.append(f"| {domain} | {len(doc_ids)} | {n_chunk} |")
    lines.append("")

    # 3. Kiem tra day du 14 truong metadata
    lines.append("## 3. Kiểm tra đầy đủ 14 trường metadata\n")
    missing_cols = [c for c in REQUIRED_14_COLS if c not in df.columns]
    lines.append(f"Cột thiếu (so với schema chuẩn 14 cột): {missing_cols if missing_cols else 'không có'}\n")
    null_counts = df[REQUIRED_14_COLS].isna().sum()
    key_fields = ["article", "citation", "allowed_roles"]
    lines.append("Kiểm tra riêng 3 trường bắt buộc cho UC3/UC4 (`article`, `citation`, `allowed_roles`):\n")
    lines.append("| Trường | Số dòng rỗng | Ví dụ |")
    lines.append("|---|---|---|")
    for f in key_fields:
        n_null = int(null_counts[f])
        example = str(df[f].dropna().iloc[0])[:80] if df[f].notna().any() else "N/A"
        lines.append(f"| `{f}` | {n_null} | {example} |")
    lines.append("")
    metadata_ok = all(int(null_counts[f]) == 0 for f in key_fields) and not missing_cols

    # 4. Tap chunks_combined_secure.csv - phan external
    lines.append("## 4. `chunks_combined_secure.csv` (dùng để retrieval đối chiếu ngoài)\n")
    is_internal = combined["document_id"].astype(str).str.startswith("agr_")
    lines.append(f"- Tổng: {len(combined)} chunk (nội bộ mô phỏng: {int(is_internal.sum())}, pháp lý bên ngoài: {int((~is_internal).sum())})")
    lines.append(f"- Phân bố `loai_van_ban` (bên ngoài): {combined.loc[~is_internal, 'loai_van_ban'].value_counts().to_dict()}\n")

    cataloging_ok = metadata_ok and not unmapped and n_docs > 0

    lines.append("## Kết luận\n")
    lines.append(f"DATA CATALOGING: {'PASS' if cataloging_ok else 'FAIL'}")
    lines.append(f"DOMAINS DETECTED: {len(domain_docs)}")
    lines.append(f"READY FOR UC3 & UC4: {'YES' if cataloging_ok else 'NO'}")

    out_path = BASE_DIR / "outputs" / "b18_data_catalog.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {out_path}")
    print("\n".join(lines[-3:]))


if __name__ == "__main__":
    main()
