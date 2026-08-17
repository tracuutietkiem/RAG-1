"""Citation dua tren metadata THAT trong corpus. Khong bia."""


def build_citation(rec: dict) -> str:
    """Uu tien cot citation da tinh o buoc chuan hoa; neu thieu thi dung lai."""
    cite = (rec.get("citation") or "").strip()
    if cite:
        return cite
    parts = []
    for key in ("title", "so_ky_hieu"):
        v = (rec.get(key) or "").strip()
        if v and v not in parts:
            parts.append(v)
    art = (rec.get("article") or "").strip()
    cl = (rec.get("clause") or "").strip()
    if art:
        parts.append(f"Điều {art}" + (f" khoản {cl}" if cl.isdigit() else ""))
    parts.append(rec.get("chunk_id", ""))
    return " | ".join(p for p in parts if p)


def attach(rec: dict, **extra) -> dict:
    """Chuan hoa mot ket qua retrieval, KHONG lam mat citation."""
    out = {
        "chunk_id": rec.get("chunk_id", ""),
        "document_id": rec.get("document_id", ""),
        "so_ky_hieu": rec.get("so_ky_hieu", ""),
        "article": rec.get("article", ""),
        "clause": rec.get("clause", ""),
        "text": rec.get("text", ""),
        "index_text": rec.get("index_text", ""),
        "citation": build_citation(rec),
    }
    out.update(extra)
    return out
