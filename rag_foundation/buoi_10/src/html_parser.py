"""Bước 1 (SPEC_buoi_10.md mục 2, 5): làm sạch HTML và chunking phân cấp.

Toàn bộ hàm ở đây là hàm THUẦN (pure) — chỉ nhận string/objects, không tự đọc
file, không gọi mạng, không phụ thuộc Neo4j hay model embedding. Vì vậy có thể
unit test 100% offline với fixture HTML nhỏ.

Cấp bậc nhận diện: Document > Chương > Mục > Điều > đoạn/bảng.

Quy tắc nhận diện heading rút kinh nghiệm từ Buổi 09 (SPEC_buoi_09.md mục 8):
- Heading phải neo ở ĐẦU văn bản của block (sau khi bỏ tiền tố Markdown '#').
- "Điều N" chỉ được coi là heading khi có dấu chấm ngay sau số ("Điều 7."),
  để không nhầm với trích dẫn chéo giữa câu kiểu "...quy định tại Điều 8...".
Đây là giả định ban đầu — PHẢI đối chiếu lại với cấu trúc HTML thật khi có dữ
liệu, vì hiện chưa có mẫu HTML thật nào trong repo (xem SPEC mục 4).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable

from bs4 import BeautifulSoup, Tag

# Thứ tự cấp bậc, số càng nhỏ càng "cao" (gần gốc văn bản hơn).
LEVEL_ORDER = {
    "document": 0,
    "chuong": 1,
    "muc": 2,
    "dieu": 3,
    "khoan": 4,
    "diem": 5,
    "doan": 6,
    "bang": 6,
}

# Cấp có thể làm cha của cấp khác (tạo nhánh trong cây).
CONTAINER_LEVELS = ("chuong", "muc", "dieu", "khoan", "diem")

_HEADING_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("chuong", re.compile(r"^#{0,6}\s*chương\s+[ivxlcdm0-9]+\b", re.IGNORECASE)),
    ("muc", re.compile(r"^#{0,6}\s*mục\s+\d+\b", re.IGNORECASE)),
    # "Điều N." bắt buộc có dấu chấm sau số — tránh bẫy đã ghi nhận ở Buổi 09.
    ("dieu", re.compile(r"^#{0,6}\s*điều\s+\d+\.", re.IGNORECASE)),
]

# Khoản/Điểm KHÔNG phải heading Markdown mà là đoạn văn mở đầu bằng số/chữ cái.
# Chỉ được coi là Khoản/Điểm khi đang nằm TRONG một Điều — nếu không sẽ nhận nhầm
# các dòng đánh số ở phần mở đầu, phụ lục hay nội dung mô tả bảng biểu.
_KHOAN_PATTERN = re.compile(r"^(\d{1,2})\.\s+\S")
_DIEM_PATTERN = re.compile(r"^([a-zđ]{1,2})\)\s+\S", re.IGNORECASE)

_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "div")


@dataclass
class RawBlock:
    """Một khối văn bản đã lấy ra từ HTML, trước khi phân loại cấp bậc."""

    text: str
    is_table: bool = False


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    level: str  # "chuong" | "muc" | "dieu" | "doan" | "bang"
    heading: str | None
    text: str
    order_index: int
    parent_id: str | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "level": self.level,
            "heading": self.heading,
            "text": self.text,
            "order_index": self.order_index,
            "parent_id": self.parent_id,
            "warnings": list(self.warnings),
        }


def clean_html(raw_html: str) -> BeautifulSoup:
    """Làm sạch HTML: bỏ script/style/comment, giữ nguyên thẻ cấu trúc.

    Không được gọi "clean" nếu làm mất heading/đoạn/bảng — chỉ loại bỏ
    thẻ không mang nội dung nghiệp vụ (script, style, thẻ điều khiển UI).
    """

    # Dùng "html.parser" (built-in chuẩn Python, không cần biên dịch C) thay vì
    # "lxml": HTML đầu vào (do md_to_html.py sinh ra hoặc HTML luật dạng chuẩn)
    # đã có cấu trúc thẻ hợp lệ, không cần khả năng phục hồi HTML lỗi nặng của
    # lxml. Tránh phụ thuộc lxml vì gói này không có sẵn wheel cho một số bản
    # Python mới trên Windows (ví dụ 3.14) và việc biên dịch từ mã nguồn đòi
    # hỏi cài thêm Microsoft C++ Build Tools — không nên bắt buộc học viên cài.
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup


def _table_to_text(table: Tag) -> str:
    """Chuyển <table> thành text dạng lưới, giữ ranh giới ô/hàng để không mất dữ liệu."""

    rows_text = []
    for row in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if any(cells):
            rows_text.append(" | ".join(cells))
    return "\n".join(rows_text)


def extract_blocks(soup: BeautifulSoup) -> list[RawBlock]:
    """Duyệt HTML theo thứ tự đọc, trả về danh sách khối văn bản thô.

    Bảng được giữ làm một khối riêng (is_table=True) — không hoà lẫn vào đoạn văn,
    vì bảng cần loại "bang" ở tầng chunk phía trên.
    """

    blocks: list[RawBlock] = []
    body = soup.body or soup
    for el in body.find_all(_BLOCK_TAGS, recursive=True):
        # Tránh nhân đôi nội dung: bỏ qua div/li chứa các block con đã được duyệt riêng.
        if el.name == "div" and el.find(_BLOCK_TAGS):
            continue
        if el.name == "table":
            text = _table_to_text(el)
            if text.strip():
                blocks.append(RawBlock(text=text, is_table=True))
            continue
        text = el.get_text(" ", strip=True)
        if text:
            blocks.append(RawBlock(text=text, is_table=False))
    return blocks


def classify_level(block: RawBlock, inside_dieu: bool = False) -> tuple[str, str | None]:
    """Trả về (level, heading_text_or_None) cho một khối văn bản thô.

    `inside_dieu`: đang nằm trong một Điều hay chưa. Chỉ khi True mới xét
    Khoản/Điểm — ngoài phạm vi Điều, các dòng "1." hay "a)" là nội dung liệt kê
    thường, không phải cấp bậc pháp lý.
    """

    if block.is_table:
        return "bang", None

    text = block.text.strip()
    for level, pattern in _HEADING_PATTERNS:
        if pattern.match(text):
            return level, text

    if inside_dieu:
        if _KHOAN_PATTERN.match(text):
            return "khoan", None
        if _DIEM_PATTERN.match(text):
            return "diem", None

    return "doan", None


def _make_chunk_id(doc_id: str, path: Iterable[str]) -> str:
    """chunk_id ổn định: hash(doc_id + đường dẫn cấp bậc). Cùng input phải ra cùng ID
    giữa các lần chạy (yêu cầu idempotent khi nạp Neo4j — SPEC mục 5)."""

    raw = doc_id + "::" + "/".join(path)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_hierarchy(doc_id: str, blocks: list[RawBlock]) -> list[Chunk]:
    """Dựng cây Chương → Mục → Điều → đoạn/bảng từ danh sách khối thô theo thứ tự đọc.

    Thuật toán stack theo cấp bậc (LEVEL_ORDER): mỗi heading mới đóng các heading
    con hiện tại trên stack có cấp thấp hơn hoặc bằng, rồi trở thành cha của các
    khối tiếp theo cho tới khi gặp heading khác cùng cấp hoặc cao hơn.

    Khối "doan"/"bang" không có heading riêng — làm con của heading gần nhất còn
    mở trên stack (mặc định là "dieu", nếu chưa có Điều nào thì lùi dần lên Mục,
    Chương, cuối cùng là gốc Document — tương tự document_fallback ở Buổi 09).
    """

    stack: list[tuple[int, str, int]] = []  # (level_rank, chunk_id, path_len)
    path: list[str] = []
    chunks: list[Chunk] = []
    order_index = 0
    counters: dict[int, int] = {}

    for block in blocks:
        inside_dieu = any(rank_on_stack >= LEVEL_ORDER["dieu"] for rank_on_stack, _, _ in stack)
        level, heading = classify_level(block, inside_dieu=inside_dieu)
        rank = LEVEL_ORDER[level]

        if level in CONTAINER_LEVELS:
            # Đóng mọi heading trên stack có cấp thấp hơn hoặc bằng heading mới.
            while stack and stack[-1][0] >= rank:
                stack.pop()
                path.pop()

            counters[rank] = counters.get(rank, 0) + 1
            slug = f"{level}{counters[rank]}"
            path.append(slug)
            chunk_id = _make_chunk_id(doc_id, path)
            parent_id = stack[-1][1] if stack else None

            chunk = Chunk(
                doc_id=doc_id,
                chunk_id=chunk_id,
                level=level,
                heading=heading,
                text=block.text,
                order_index=order_index,
                parent_id=parent_id,
            )
            chunks.append(chunk)
            stack.append((rank, chunk_id, len(path)))
            order_index += 1
            continue

        # doan / bang: gắn vào heading gần nhất còn mở; nếu stack rỗng thì
        # document_fallback (parent_id=None, tương đương gắn thẳng vào Document).
        parent_id = stack[-1][1] if stack else None
        warnings = [] if stack else ["document_fallback: chưa có heading cha nào"]
        counters[99] = counters.get(99, 0) + 1
        leaf_chunk_id = _make_chunk_id(doc_id, path + [f"{level}{counters[99]}"])

        chunk = Chunk(
            doc_id=doc_id,
            chunk_id=leaf_chunk_id,
            level=level,
            heading=None,
            text=block.text,
            order_index=order_index,
            parent_id=parent_id,
            warnings=warnings,
        )
        chunks.append(chunk)
        order_index += 1

    return chunks


def extract_doc_meta(raw_html: str) -> dict[str, str]:
    """Đọc các thẻ <meta name="doc-id"|"issue-number"|"doc-type"|"source-note">.

    HTML sinh bởi `md_to_html.py` luôn có các thẻ này. HTML do người dùng cung
    cấp có thể không có — khi đó trả dict rỗng và caller phải tự quyết định
    doc_id (không được im lặng bịa số hiệu văn bản).
    """

    soup = BeautifulSoup(raw_html, "html.parser")
    meta: dict[str, str] = {}
    for name in ("doc-id", "issue-number", "doc-type", "source-note"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            meta[name] = tag["content"]
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        meta["title"] = title_tag.get_text(strip=True)
    return meta


def parse_html_document(doc_id: str, raw_html: str) -> list[Chunk]:
    """Hàm tổng hợp Bước 1: HTML thô → danh sách Chunk phân cấp đã làm sạch."""

    soup = clean_html(raw_html)
    blocks = extract_blocks(soup)
    return build_hierarchy(doc_id, blocks)


def print_sample(chunks: list[Chunk], limit: int = 10) -> None:
    """In ra console kết quả phân tách mẫu — YÊU CẦU BẮT BUỘC của đề bài Bước 1
    (buoi_10.md, mục "Yêu cầu"), để minh hoạ trực quan cách chunk hoạt động."""

    print(f"--- Mẫu {min(limit, len(chunks))}/{len(chunks)} chunk đầu tiên ---")
    for c in chunks[:limit]:
        preview = c.text if len(c.text) <= 80 else c.text[:77] + "..."
        print(
            f"[{c.order_index:03d}] level={c.level:<6} parent={c.parent_id!s:<18} "
            f"id={c.chunk_id} heading={c.heading!r} text={preview!r}"
        )
        if c.warnings:
            print(f"       warnings={c.warnings}")
