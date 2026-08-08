"""chunking.py — Ba chiến lược chunking demo: fixed-size, semantic, hierarchical.

Mỗi chunk trả về là 1 dict với các khoá: chunk_id, strategy, source, page_start,
page_end, text, structure_path, structure_detected (theo SPEC_buoi_05.md).
"""

from __future__ import annotations

import bisect
import re

# ---------------------------------------------------------------------------
# Tiện ích dùng chung: ghép text nhiều trang thành 1 chuỗi + map offset -> trang
# ---------------------------------------------------------------------------


def _build_full_text(pages) -> tuple[str, list[int], list[int]]:
    """
    Trả về (full_text, start_offsets, page_numbers) — hai danh sách song song,
    tăng dần theo offset, dùng để tra cứu nhị phân trang chứa 1 vị trí ký tự.
    """
    parts: list[str] = []
    start_offsets: list[int] = []
    page_numbers: list[int] = []
    cursor = 0
    for p in pages:
        start_offsets.append(cursor)
        page_numbers.append(p.page)
        parts.append(p.text)
        cursor += len(p.text)
        parts.append("\n\n")
        cursor += 2
    return "".join(parts), start_offsets, page_numbers


def _page_at(offset: int, start_offsets: list[int], page_numbers: list[int]) -> int:
    if not start_offsets:
        return 0
    idx = bisect.bisect_right(start_offsets, offset) - 1
    idx = max(idx, 0)
    return page_numbers[idx]


# ---------------------------------------------------------------------------
# 1) Fixed-size: cắt theo số ký tự cố định, có overlap
# ---------------------------------------------------------------------------


def fixed_size_chunks(pages, source: str, chunk_size: int = 800, overlap: int = 120) -> list[dict]:
    if overlap >= chunk_size:
        raise ValueError("overlap phải nhỏ hơn chunk_size")

    full_text, start_offsets, page_numbers = _build_full_text(pages)
    if not full_text.strip():
        return []

    chunks: list[dict] = []
    idx = 0
    start = 0
    n = len(full_text)
    while start < n:
        end = min(start + chunk_size, n)
        text = full_text[start:end]
        if text.strip():
            idx += 1
            chunks.append(
                {
                    "chunk_id": f"{source}_fixed_size_{idx:04d}",
                    "strategy": "fixed_size",
                    "source": source,
                    "page_start": _page_at(start, start_offsets, page_numbers),
                    "page_end": _page_at(max(end - 1, start), start_offsets, page_numbers),
                    "text": text,
                    "structure_path": None,
                    "structure_detected": None,
                }
            )
        if end == n:
            break
        start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# 2) Semantic: ưu tiên ranh giới đoạn văn (dòng trống), gộp tới gần max_chunk_size
# ---------------------------------------------------------------------------

_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")


MIN_PARAGRAPH_LEN = 20  # đoạn văn ngắn hơn (vd số trang lẻ do OCR tách nhầm) sẽ gộp vào đoạn liền kề


def _merge_tiny_paragraphs(
    paragraphs: list[tuple[int, str]], min_len: int = MIN_PARAGRAPH_LEN
) -> list[tuple[int, str]]:
    """Gộp các đoạn văn quá ngắn (thường là số trang/footer OCR tách nhầm) vào đoạn trước đó."""
    if not paragraphs:
        return paragraphs
    merged: list[tuple[int, str]] = [paragraphs[0]]
    for offset, para in paragraphs[1:]:
        if len(para.strip()) < min_len:
            prev_offset, prev_para = merged[-1]
            merged[-1] = (prev_offset, prev_para + "\n\n" + para)
        else:
            merged.append((offset, para))
    return merged


def semantic_chunks(pages, source: str, max_chunk_size: int = 1000) -> list[dict]:
    full_text, start_offsets, page_numbers = _build_full_text(pages)
    if not full_text.strip():
        return []

    paragraphs: list[tuple[int, str]] = []
    pos = 0
    for m in _PARA_SPLIT_RE.finditer(full_text):
        para = full_text[pos : m.start()]
        if para.strip():
            paragraphs.append((pos, para))
        pos = m.end()
    tail = full_text[pos:]
    if tail.strip():
        paragraphs.append((pos, tail))
    if not paragraphs:
        paragraphs = [(0, full_text)]
    paragraphs = _merge_tiny_paragraphs(paragraphs)

    chunks: list[dict] = []
    idx = 0
    buf_start_offset: int | None = None
    buf_parts: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal idx, buf_start_offset, buf_parts, buf_len
        if not buf_parts:
            return
        text = "\n\n".join(buf_parts).strip()
        if text and buf_start_offset is not None:
            idx += 1
            end_offset = buf_start_offset + len(text)
            chunks.append(
                {
                    "chunk_id": f"{source}_semantic_{idx:04d}",
                    "strategy": "semantic",
                    "source": source,
                    "page_start": _page_at(buf_start_offset, start_offsets, page_numbers),
                    "page_end": _page_at(
                        max(end_offset - 1, buf_start_offset), start_offsets, page_numbers
                    ),
                    "text": text,
                    "structure_path": None,
                    "structure_detected": None,
                }
            )
        buf_parts = []
        buf_len = 0
        buf_start_offset = None

    for offset, para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue
        if buf_len and buf_len + len(para_stripped) > max_chunk_size:
            flush()
        if buf_start_offset is None:
            buf_start_offset = offset
        buf_parts.append(para_stripped)
        buf_len += len(para_stripped)
    flush()
    return chunks


# ---------------------------------------------------------------------------
# 3) Hierarchical: Chương -> Mục -> Điều -> Khoản -> Điểm
#
# LƯU Ý QUAN TRỌNG (phát hiện qua review thực tế trên văn bản luật thật):
# Trong văn bản pháp luật Việt Nam, "Chương"/"Mục"/"Điều" LÀ tiêu đề thật, luôn
# đứng ở ĐẦU DÒNG. Nhưng "khoản" và "điểm" hầu như KHÔNG xuất hiện dưới dạng chữ
# "Khoản 5"/"Điểm a)" ở đầu mục — chúng chỉ được đánh số/chữ cái trần ("1.", "a)")
# và chữ "khoản"/"điểm" chủ yếu xuất hiện TRONG CÂU khi trích dẫn chéo (vd:
# "...trừ các đối tác quy định tại khoản 7 Điều này"). Nếu match theo từ khoá
# "Khoản \d+"/"Điểm x)" ở BẤT KỲ vị trí nào trong text (không neo đầu dòng) sẽ
# bắt nhầm các câu trích dẫn chéo này thành tiêu đề mới, làm gãy chunk sai
# (từng gặp: chunk chỉ còn text "khoản 4"). Vì vậy:
# - Chương/Mục/Điều: bắt buộc đứng ở đầu dòng (có thể có tiền tố Markdown '#'
#   do LlamaParse sinh ra); Điều bắt buộc có dấu chấm ngay sau số (phân biệt
#   tiêu đề "Điều 8. ..." với câu trích dẫn "...Điều 8 Thông tư này").
# - Khoản/Điểm: nhận diện qua định dạng liệt kê thật ở đầu dòng ("1. ", "a) "),
#   KHÔNG dựa vào từ khoá "khoản"/"điểm".
# ---------------------------------------------------------------------------

_HEADING_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
    (0, re.compile(r"^#{0,6}\s*(Ch[uư][ơo]ng\s+[IVXLCDM\d]+)\b", re.MULTILINE | re.IGNORECASE)),
    (1, re.compile(r"^#{0,6}\s*(Mục\s+\d+)\b", re.MULTILINE | re.IGNORECASE)),
    (2, re.compile(r"^#{0,6}\s*(Điều\s+\d+[a-zđ]?)\.", re.MULTILINE | re.IGNORECASE)),
    (3, re.compile(r"^\s*(\d{1,3})\.\s+\S", re.MULTILINE)),
    (4, re.compile(r"^\s*([a-zđ])\)\s+\S", re.MULTILINE)),
]

def _collect_heading_matches(full_text: str) -> list[tuple[int, int, str]]:
    """Trả về [(offset, level, label)] đã sắp xếp theo offset tăng dần."""
    found: list[tuple[int, int, str]] = []
    for level, pattern in _HEADING_PATTERNS:
        for m in pattern.finditer(full_text):
            group_text = m.group(1).strip()
            if level == 3:  # khoản: group_text là số, vd "1" -> "Khoản 1"
                label = f"Khoản {group_text}"
            elif level == 4:  # điểm: group_text là chữ cái, vd "a" -> "Điểm a)"
                label = f"Điểm {group_text})"
            else:
                label = " ".join(group_text.split())
            found.append((m.start(), level, label))
    found.sort(key=lambda t: t[0])
    return found


def hierarchical_chunks(pages, source: str) -> list[dict]:
    full_text, start_offsets, page_numbers = _build_full_text(pages)
    if not full_text.strip():
        return []

    matches = _collect_heading_matches(full_text)
    if not matches:
        # Không phát hiện mốc cấu trúc nào — KHÔNG bịa heading, trả 1 chunk + cảnh báo.
        return [
            {
                "chunk_id": f"{source}_hierarchical_0001",
                "strategy": "hierarchical",
                "source": source,
                "page_start": page_numbers[0],
                "page_end": page_numbers[-1],
                "text": full_text.strip(),
                "structure_path": None,
                "structure_detected": False,
            }
        ]

    chunks: list[dict] = []
    idx = 0
    # current[level] = nhãn mốc đang có hiệu lực ở level đó. Dùng dict thay vì
    # list cố định để KHÔNG chèn placeholder khi thiếu cấp trung gian (ví dụ
    # văn bản có Chương -> Điều nhưng không có Mục).
    current: dict[int, str] = {}
    boundaries = [start for start, _, _ in matches] + [len(full_text)]

    for i, (start, level, label) in enumerate(matches):
        # Bỏ các mốc cấp sâu hơn hoặc bằng level hiện tại (mốc mới thay thế mốc cũ cùng cấp).
        for lvl in [lvl for lvl in current if lvl >= level]:
            del current[lvl]
        current[level] = label

        end = boundaries[i + 1]
        text = full_text[start:end].strip()
        if not text:
            continue
        idx += 1
        structure_path = " > ".join(current[lvl] for lvl in sorted(current))
        chunks.append(
            {
                "chunk_id": f"{source}_hierarchical_{idx:04d}",
                "strategy": "hierarchical",
                "source": source,
                "page_start": _page_at(start, start_offsets, page_numbers),
                "page_end": _page_at(max(end - 1, start), start_offsets, page_numbers),
                "text": text,
                "structure_path": structure_path,
                "structure_detected": True,
            }
        )
    return chunks
