"""Công cụ cầu nối: sinh HTML đầu vào cho Buổi 10 từ kết quả OCR của Buổi 05.

LÝ DO TỒN TẠI (đọc kỹ trước khi dùng):

Đề bài Buổi 10 yêu cầu đầu vào là văn bản luật dạng HTML. Repo hiện chỉ có PDF
`2026-08-01_TaiLieu_NHNNSigned.pdf` (Thông tư 41/2016/TT-NHNN). Lớp text của PDF
đó hỏng nặng (mất dấu tiếng Việt: "Di~u 1" thay vì "Điều 1"), KHÔNG dùng trực
tiếp được. Buổi 05 đã chạy OCR ra bản markdown tiếng Việt sạch tại
`buoi_05/output/raw/*.json` — module này chuyển bản sạch đó sang HTML.

RÀNG BUỘC:
- CHỈ ĐỌC từ `buoi_05/output/`, tuyệt đối không ghi gì vào thư mục Buổi 05.
- Không "sửa" nội dung pháp lý. Chỉ đổi định dạng markdown → thẻ HTML tương ứng.
- Bảng trong nguồn đã ở dạng HTML sẵn (thẻ <table>) nên được giữ nguyên vẹn.
- HTML sinh ra là dữ liệu phái sinh từ OCR, CÓ THỂ còn lỗi nhận dạng. Mọi trích
  dẫn về sau phải đối chiếu văn bản gốc trước khi dùng cho công việc.

Chạy: python -m src.md_to_html --raw <duong_dan_raw.json> --out data/raw_html/
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# "Căn cứ <loại VB> ... số <số hiệu> ngày ..." trong phần mở đầu văn bản.
_CAN_CU_PATTERN = re.compile(
    r"^Căn cứ\s+(?P<body>.+?)[;.]?\s*$",
    re.IGNORECASE,
)
# Số hiệu văn bản: 46/2010/QH12, 156/2013/NĐ-CP, 41/2016/TT-NHNN...
# Hậu tố PHẢI cho phép chữ số ("QH12"), nếu chỉ [A-ZĐ\-]* thì \b cuối không khớp
# do "H" và "1" đều là ký tự từ — lỗi này đã xảy ra thật khi chạy lần đầu.
_DOC_NUMBER_PATTERN = re.compile(r"\b(\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ][A-Z0-9Đ\-]*)")
_SELF_NUMBER_PATTERN = re.compile(r"^Số:\s*(?P<num>\S.*?)\s*$", re.MULTILINE)


@dataclass
class SourceDocInfo:
    """Metadata rút từ chính văn bản, phục vụ tạo node (:Document) và quan hệ."""

    doc_id: str
    title: str
    doc_type: str | None
    issue_number: str | None
    can_cu_refs: list[dict] = field(default_factory=list)


def load_raw_markdown(raw_json_path: Path) -> str:
    """Ghép text các trang từ file raw JSON của Buổi 05 thành một markdown liền mạch."""

    data = json.loads(raw_json_path.read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    return "\n\n".join(p.get("text", "") for p in pages)


def _normalize_doc_number(num: str) -> str:
    return re.sub(r"\s+", "", num)


def _doc_type_from_suffix(suffix: str) -> str | None:
    """Suy loại văn bản từ hậu tố số hiệu. Chỉ ánh xạ các hậu tố chắc chắn;
    hậu tố lạ trả None thay vì đoán bừa."""

    suffix = suffix.upper()
    if suffix.startswith("QH"):
        return "Luật"
    return {
        "NĐ-CP": "Nghị định",
        "ND-CP": "Nghị định",
        "TT-NHNN": "Thông tư",
        "QĐ-NHNN": "Quyết định",
        "QD-NHNN": "Quyết định",
    }.get(suffix)


def extract_doc_info(markdown: str, fallback_title: str) -> SourceDocInfo:
    """Rút số hiệu văn bản và danh sách văn bản được viện dẫn ở phần 'Căn cứ ...'.

    Các văn bản được viện dẫn sẽ trở thành node (:Document) dạng stub (chỉ có
    metadata, không có Chunk) và nối bằng quan hệ [:CAN_CU]. Đây là dữ liệu THẬT
    lấy từ chính phần mở đầu văn bản, không phải số liệu tự bịa.
    """

    self_match = _SELF_NUMBER_PATTERN.search(markdown)
    issue_number = _normalize_doc_number(self_match.group("num")) if self_match else None

    title = fallback_title
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped.lower().startswith("quy định"):
            title = stripped
            break

    refs: list[dict] = []
    seen: set[str] = set()
    for line in markdown.splitlines():
        line = line.strip()
        if not line.lower().startswith("căn cứ"):
            continue
        m = _CAN_CU_PATTERN.match(line)
        if not m:
            continue
        body = m.group("body").strip()
        num_match = _DOC_NUMBER_PATTERN.search(body)
        if not num_match:
            # Không có số hiệu -> không đủ định danh để tạo node Document riêng.
            continue
        ref_number = _normalize_doc_number(num_match.group(1))
        if ref_number in seen:
            continue
        seen.add(ref_number)
        refs.append(
            {
                "issue_number": ref_number,
                "title": body,
                "doc_type": _doc_type_from_suffix(ref_number.split("/")[-1]),
            }
        )

    doc_id = issue_number or fallback_title
    doc_type = None
    if issue_number:
        tail = issue_number.split("/")[-1].upper()
        doc_type = _doc_type_from_suffix(tail)

    return SourceDocInfo(
        doc_id=doc_id,
        title=title,
        doc_type=doc_type,
        issue_number=issue_number,
        can_cu_refs=refs,
    )


def markdown_to_html_body(markdown: str) -> str:
    """Chuyển markdown OCR sang HTML, giữ nguyên cấu trúc heading/đoạn/bảng.

    Quy tắc ánh xạ:
      '# Chương I'          -> <h1>
      '## Điều 7. ...'      -> <h2>
      '<table>...</table>'  -> giữ nguyên khối HTML, không đụng vào
      dòng thường           -> <p>
    """

    lines = markdown.splitlines()
    out: list[str] = []
    in_table = False
    table_buf: list[str] = []

    for line in lines:
        stripped = line.strip()

        if in_table:
            table_buf.append(line)
            if "</table>" in stripped.lower():
                out.append("\n".join(table_buf))
                table_buf = []
                in_table = False
            continue

        if stripped.lower().startswith("<table"):
            in_table = True
            table_buf = [line]
            continue

        if not stripped:
            continue

        heading_match = re.match(r"^(#{1,6})\s*(.+)$", stripped)
        if heading_match:
            level = min(len(heading_match.group(1)), 6)
            text = heading_match.group(2).strip()
            out.append(f"<h{level}>{html_lib.escape(text)}</h{level}>")
            continue

        # Bỏ đánh dấu in đậm/nghiêng của markdown, giữ nguyên nội dung chữ.
        text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", stripped)
        out.append(f"<p>{html_lib.escape(text)}</p>")

    if table_buf:  # bảng thiếu thẻ đóng — vẫn giữ lại, không bỏ dữ liệu
        out.append("\n".join(table_buf))

    return "\n".join(out)


def build_html_document(info: SourceDocInfo, body_html: str, source_note: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>{html_lib.escape(info.title)}</title>
<meta name="doc-id" content="{html_lib.escape(info.doc_id)}">
<meta name="issue-number" content="{html_lib.escape(info.issue_number or '')}">
<meta name="doc-type" content="{html_lib.escape(info.doc_type or '')}">
<meta name="source-note" content="{html_lib.escape(source_note)}">
</head>
<body>
{body_html}
</body>
</html>
"""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Sinh HTML đầu vào Buổi 10 từ kết quả OCR Buổi 05 (chỉ đọc)."
    )
    parser.add_argument("--raw", required=True, help="Đường dẫn buoi_05/output/raw/*.json")
    parser.add_argument("--out", default="data/raw_html", help="Thư mục HTML đầu ra")
    parser.add_argument(
        "--relationships-out",
        default="data/doc_relationships.json",
        help="File khai báo quan hệ liên văn bản sinh từ phần 'Căn cứ ...'",
    )
    args = parser.parse_args(argv)

    raw_path = Path(args.raw)
    markdown = load_raw_markdown(raw_path)
    info = extract_doc_info(markdown, fallback_title=raw_path.stem)
    body_html = markdown_to_html_body(markdown)

    source_note = (
        "Phái sinh từ OCR Buổi 05 của "
        f"{raw_path.name}. Có thể còn lỗi nhận dạng — phải đối chiếu văn bản gốc."
    )
    html_text = build_html_document(info, body_html, source_note)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^0-9A-Za-z]+", "_", info.doc_id).strip("_") or raw_path.stem
    out_file = out_dir / f"{safe_name}.html"
    out_file.write_text(html_text, encoding="utf-8")

    rel_path = Path(args.relationships_out)
    rel_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "documents": [
            {
                "doc_id": info.doc_id,
                "title": info.title,
                "doc_type": info.doc_type,
                "issue_number": info.issue_number,
                "has_chunks": True,
                "source_file": out_file.name,
            }
        ]
        + [
            {
                "doc_id": ref["issue_number"],
                "title": ref["title"],
                "doc_type": ref.get("doc_type"),
                "issue_number": ref["issue_number"],
                "has_chunks": False,
                "source_file": None,
                "note": "Node stub — văn bản được viện dẫn, chưa nạp toàn văn",
            }
            for ref in info.can_cu_refs
        ],
        "relationships": [
            {"from": info.doc_id, "type": "CAN_CU", "to": ref["issue_number"]}
            for ref in info.can_cu_refs
        ],
    }
    rel_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Đã ghi HTML: {out_file}")
    print(f"Đã ghi quan hệ: {rel_path}")
    print(f"doc_id={info.doc_id} | doc_type={info.doc_type} | title={info.title!r}")
    print(f"Số văn bản viện dẫn (CAN_CU): {len(info.can_cu_refs)}")
    for ref in info.can_cu_refs:
        print(f"  - {ref['issue_number']}: {ref['title'][:70]}...")


if __name__ == "__main__":
    main()
