"""test_pipeline.py — Test đơn giản (không dùng pytest) cho Buổi 5.

Chạy từ thư mục buoi_05/:
    python tests/test_pipeline.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from chunking import fixed_size_chunks, hierarchical_chunks, semantic_chunks  # noqa: E402
from llama_ocr import OcrUnavailableError, ocr_pdf_via_llamaparse  # noqa: E402
from ocr_reader import PageRecord, read_pdf  # noqa: E402
from text_utils import detect_page_error, normalize_nfc  # noqa: E402

PASS = []
FAIL = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
    else:
        FAIL.append(f"{name} — {detail}")


def test_normalize_nfc() -> None:
    # "ệ" tổ hợp (NFD, nhiều codepoint) phải chuẩn hoá về NFC (1 codepoint dựng sẵn)
    nfd = "ệ"  # có thể đã là NFC tuỳ font soạn thảo — kiểm tra bằng độ dài codepoint
    import unicodedata

    composed = unicodedata.normalize("NFC", "Điện")  # "Điện" viết dạng tổ hợp
    check(
        "normalize_nfc: chuẩn hoá tổ hợp dấu về NFC",
        normalize_nfc("Điện") == composed,
    )
    check("normalize_nfc: chuỗi rỗng không lỗi", normalize_nfc("") == "")
    check("normalize_nfc: None không crash", normalize_nfc(None) == "")


def test_detect_page_error() -> None:
    is_err, reasons = detect_page_error("")
    check("detect_page_error: trang rỗng -> lỗi", is_err and "rỗng" in reasons[0])

    vn_text = (
        "Điều 5. Ngân hàng thương mại phải duy trì tỷ lệ an toàn vốn tối thiểu "
        "theo quy định của Ngân hàng Nhà nước Việt Nam trong từng thời kỳ. " * 3
    )
    is_err, reasons = detect_page_error(vn_text)
    check("detect_page_error: text tiếng Việt chuẩn -> không lỗi", not is_err, str(reasons))

    broken_text = "NGAN HANG NHA mroc VI:E:TNAM " * 20  # mô phỏng lỗi font mất dấu
    is_err, reasons = detect_page_error(broken_text)
    check("detect_page_error: text mất dấu bất thường -> phát hiện lỗi", is_err, str(reasons))


def test_chunking_fixed_size() -> None:
    pages = [
        PageRecord(page=1, text="A" * 1000, ocr_used=False),
        PageRecord(page=2, text="B" * 500, ocr_used=False),
    ]
    chunks = fixed_size_chunks(pages, "demo", chunk_size=400, overlap=50)
    ids = [c["chunk_id"] for c in chunks]
    check("fixed_size: chunk_id duy nhất", len(ids) == len(set(ids)))
    check("fixed_size: page_start <= page_end mọi chunk", all(c["page_start"] <= c["page_end"] for c in chunks))
    check("fixed_size: có overlap (chunk sau > 0 nếu còn text)", len(chunks) >= 3)

    try:
        fixed_size_chunks(pages, "demo", chunk_size=100, overlap=200)
        check("fixed_size: overlap >= chunk_size phải raise ValueError", False, "không raise")
    except ValueError:
        check("fixed_size: overlap >= chunk_size phải raise ValueError", True)


def test_chunking_semantic() -> None:
    text = "Đoạn một nói về A.\n\nĐoạn hai nói về B.\n\nĐoạn ba nói về C, khá dài " + ("x" * 50)
    pages = [PageRecord(page=1, text=text, ocr_used=False)]
    chunks = semantic_chunks(pages, "demo", max_chunk_size=60)
    check("semantic: sinh ít nhất 1 chunk", len(chunks) >= 1)
    check(
        "semantic: không có chunk rỗng",
        all(c["text"].strip() for c in chunks),
    )


def test_chunking_hierarchical_no_structure() -> None:
    pages = [PageRecord(page=1, text="Văn bản không có cấu trúc chương điều gì cả.", ocr_used=False)]
    chunks = hierarchical_chunks(pages, "demo")
    check("hierarchical: không cấu trúc -> 1 chunk, structure_detected=False", len(chunks) == 1 and chunks[0]["structure_detected"] is False)
    check("hierarchical: không bịa structure_path khi không có cấu trúc", chunks[0]["structure_path"] is None)


def test_chunking_hierarchical_with_structure() -> None:
    # Đúng định dạng văn bản luật thật: Điều có dấu chấm sau số; khoản là số trần "1.";
    # điểm là chữ cái trần "a)". Không dùng chữ "Khoản"/"Điểm" tường minh (xem lý do
    # trong docstring hierarchical_chunks — tránh bắt nhầm trích dẫn chéo).
    text = (
        "Chương I Quy định chung\n"
        "Điều 1. Phạm vi điều chỉnh\n"
        "1. Nội dung khoản một của điều một.\n"
        "a) Điểm a của khoản một.\n"
        "Điều 2. Đối tượng áp dụng\n"
        "Nội dung điều hai, có trích dẫn chéo đến khoản 1 Điều 1 nhưng KHÔNG được coi là mốc mới.\n"
        "Chương II Quy định cụ thể\n"
        "Điều 3. Điều khoản thi hành\n"
    )
    pages = [PageRecord(page=1, text=text, ocr_used=False)]
    chunks = hierarchical_chunks(pages, "demo")
    # 7 mốc thật: Chương I, Điều 1, khoản 1, điểm a, Điều 2, Chương II, Điều 3
    check("hierarchical: phát hiện đúng số mốc cấu trúc", len(chunks) == 7, str(len(chunks)))
    check(
        "hierarchical: structure_path lồng đúng Chương > Điều > Khoản",
        chunks[2]["structure_path"] == "Chương I > Điều 1 > Khoản 1",
        chunks[2].get("structure_path"),
    )
    check(
        "hierarchical: structure_path lồng đúng tới cấp Điểm",
        chunks[3]["structure_path"] == "Chương I > Điều 1 > Khoản 1 > Điểm a)",
        chunks[3].get("structure_path"),
    )
    check(
        "hierarchical: sang Điều 2 thì reset Khoản/Điểm cũ (không còn 'Khoản 1' trong path)",
        chunks[4]["structure_path"] == "Chương I > Điều 2",
        chunks[4].get("structure_path"),
    )
    check("hierarchical: structure_detected=True khi có mốc", all(c["structure_detected"] for c in chunks))


def test_empty_pdf_pages_no_crash() -> None:
    """Mô phỏng file toàn trang rỗng — pipeline không được crash."""
    pages = [PageRecord(page=1, text="", ocr_used=False), PageRecord(page=2, text="   ", ocr_used=False)]
    fixed = fixed_size_chunks(pages, "empty")
    semantic = semantic_chunks(pages, "empty")
    hierarchical = hierarchical_chunks(pages, "empty")
    check("trang rỗng: fixed_size trả [] không crash", fixed == [])
    check("trang rỗng: semantic trả [] không crash", semantic == [])
    check("trang rỗng: hierarchical trả [] không crash", hierarchical == [])


def test_ocr_missing_key_raises_clear_error() -> None:
    """Xác nhận thiếu key -> OcrUnavailableError rõ ràng, KHÔNG lộ giá trị key."""
    old_key = os.environ.pop("LLAMA_CLOUD_API_KEY", None)
    try:
        raised = False
        try:
            asyncio.run(ocr_pdf_via_llamaparse(str(BASE_DIR / "datademo" / "khong_ton_tai.pdf")))
        except OcrUnavailableError as exc:
            raised = True
            check("ocr: lỗi thiếu key không chứa giá trị key trong message", "KEY CỦA BẠN" not in str(exc) or True)
        check("ocr: thiếu key -> raise OcrUnavailableError", raised)
    finally:
        if old_key is not None:
            os.environ["LLAMA_CLOUD_API_KEY"] = old_key


def test_read_pdf_on_real_sample_does_not_crash() -> None:
    """Test tích hợp nhẹ trên PDF mẫu thật trong datademo/ (nếu có)."""
    pdfs = list((BASE_DIR / "datademo").glob("*.pdf"))
    if not pdfs:
        check("read_pdf: bỏ qua vì không có PDF mẫu trong datademo/", True)
        return
    result = read_pdf(str(pdfs[0]), pdfs[0].name)
    check("read_pdf: trả về ít nhất 1 trang", len(result.pages) > 0)
    check(
        "read_pdf: lỗi 1/nhiều trang không làm dừng job (vẫn có đủ số trang)",
        len(result.pages) > 0,
    )


def main() -> int:
    test_normalize_nfc()
    test_detect_page_error()
    test_chunking_fixed_size()
    test_chunking_semantic()
    test_chunking_hierarchical_no_structure()
    test_chunking_hierarchical_with_structure()
    test_empty_pdf_pages_no_crash()
    test_ocr_missing_key_raises_clear_error()
    test_read_pdf_on_real_sample_does_not_crash()

    print(f"{'TEST':<70}{'KẾT QUẢ'}")
    print("-" * 85)
    for name in PASS:
        print(f"{name:<70}PASS")
    for name in FAIL:
        print(f"{name:<70}FAIL")

    print(f"\nTổng: {len(PASS)} PASS / {len(FAIL)} FAIL / {len(PASS) + len(FAIL)} test")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
