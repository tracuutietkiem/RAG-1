"""
BUOI 17 - PROMPT 6: Kiem tra du lieu co du cho Compliance Gap Analysis khong.

Phan loai TUNG document theo evidence THAT (loai_van_ban, co_quan_ban_hanh,
document_id) - KHONG duoc goi mot Thong tu/Nghi dinh la "quy dinh noi bo" chi
de chay demo.

Nguon: data/chunks_combined_secure.csv (787 external + 24 internal, da chuan
bi rieng cho Buoi 17 - xem outputs/dependency_report.md muc 4).

Xuat: outputs/gap_input_catalog.md
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
COMBINED_CSV = BASE_DIR / "data" / "chunks_combined_secure.csv"
OUT = BASE_DIR / "outputs" / "gap_input_catalog.md"

EXTERNAL_TYPES = {"Thông tư", "Nghị định", "Luật", "Văn bản hợp nhất"}
INTERNAL_TYPES = {"Quy định nội bộ", "Quy chế nội bộ"}


def classify(row) -> tuple[str, str]:
    """Tra ve (classification, evidence). Fail-safe: khong khop loai nao ro
    rang -> UNKNOWN, khong ep ve EXTERNAL/INTERNAL mot cach vo can cu."""
    lvb = str(row.get("loai_van_ban", "")).strip()
    doc_id = str(row.get("document_id", ""))
    issuer = str(row.get("co_quan_ban_hanh", "")).strip()

    if lvb in INTERNAL_TYPES or doc_id.startswith("agr_"):
        evidence = f"loai_van_ban='{lvb}', document_id='{doc_id}' bắt đầu bằng 'agr_' (nguồn: agribank_internal_policies.csv, MÔ PHỎNG), co_quan_ban_hanh='{issuer}'"
        return "INTERNAL_POLICY", evidence
    if lvb in EXTERNAL_TYPES:
        evidence = f"loai_van_ban='{lvb}' (thuộc {EXTERNAL_TYPES}), co_quan_ban_hanh='{issuer}'"
        return "EXTERNAL_REQUIREMENT", evidence
    return "UNKNOWN", f"loai_van_ban='{lvb}' không khớp danh mục đã biết — cần rà soát thủ công"


def main() -> None:
    df = pd.read_csv(COMBINED_CSV)
    classifications = df.apply(classify, axis=1, result_type="expand")
    df["classification"] = classifications[0]
    df["evidence"] = classifications[1]

    by_doc = (
        df.groupby("document_id")
        .agg(
            title=("title", "first"),
            loai_van_ban=("loai_van_ban", "first"),
            co_quan_ban_hanh=("co_quan_ban_hanh", "first"),
            classification=("classification", "first"),
            evidence=("evidence", "first"),
            n_chunks=("chunk_id", "count"),
        )
        .reset_index()
    )

    lines = ["# Buổi 17 — Gap Input Catalog (PROMPT 6)\n"]
    lines.append(f"Nguồn: `{COMBINED_CSV.relative_to(BASE_DIR)}` — {len(df)} chunk / {len(by_doc)} document.\n")

    n_external = int((by_doc["classification"] == "EXTERNAL_REQUIREMENT").sum())
    n_internal = int((by_doc["classification"] == "INTERNAL_POLICY").sum())
    n_unknown = int((by_doc["classification"] == "UNKNOWN").sum())

    lines.append(f"- EXTERNAL_REQUIREMENT: {n_external} document")
    lines.append(f"- INTERNAL_POLICY: {n_internal} document")
    lines.append(f"- UNKNOWN (cần rà soát thủ công, KHÔNG dùng cho gap check): {n_unknown} document")
    lines.append("")

    lines.append(
        "**Lưu ý bắt buộc**: `INTERNAL_POLICY` ở đây đến từ `agribank_internal_policies.csv` — "
        "dữ liệu **MÔ PHỎNG** do học viên tự soạn cho bài thực hành (không phải văn bản nội bộ "
        "thật của Agribank), đúng như nguyên tắc \"policy trong bài là mô phỏng\" của Buổi 17. "
        "Không có Thông tư/Nghị định nào bị gán nhãn INTERNAL_POLICY chỉ để chạy demo.\n"
    )

    lines.append("## Danh mục đầy đủ theo document\n")
    lines.append("| document_id | title (rút gọn) | loại văn bản | cơ quan ban hành | classification | n_chunks |")
    lines.append("|---|---|---|---|---|---|")
    for _, r in by_doc.sort_values(["classification", "document_id"]).iterrows():
        title = str(r["title"])[:60]
        lines.append(
            f"| {r['document_id']} | {title} | {r['loai_van_ban']} | {r['co_quan_ban_hanh']} | "
            f"{r['classification']} | {r['n_chunks']} |"
        )
    lines.append("")

    lines.append("## Evidence phân loại (mẫu 5 dòng mỗi loại)\n")
    for cls in ("EXTERNAL_REQUIREMENT", "INTERNAL_POLICY", "UNKNOWN"):
        sub = by_doc[by_doc["classification"] == cls].head(5)
        if len(sub):
            lines.append(f"### {cls}\n")
            for _, r in sub.iterrows():
                lines.append(f"- `{r['document_id']}`: {r['evidence']}")
            lines.append("")

    data_ready = n_internal > 0 and n_external > 0
    lines.append("## Kết luận\n")
    if data_ready:
        lines.append(
            f"Có đủ cả hai phía bằng chứng thật ({n_external} external, {n_internal} internal) "
            "để chạy Compliance Gap Checker."
        )
        lines.append("\nCOMPLIANCE GAP DATA: READY")
    else:
        lines.append("Thiếu một trong hai phía bằng chứng — KHÔNG kết luận compliance trên corpus này.")
        lines.append("\nCOMPLIANCE GAP DATA: INSUFFICIENT")
        lines.append("DATA GAP: INTERNAL POLICY NOT FOUND" if n_internal == 0 else "DATA GAP: EXTERNAL REQUIREMENT NOT FOUND")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print(f"EXTERNAL={n_external} INTERNAL={n_internal} UNKNOWN={n_unknown}")
    print("READY" if data_ready else "INSUFFICIENT")


if __name__ == "__main__":
    main()
