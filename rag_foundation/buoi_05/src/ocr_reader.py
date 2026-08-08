"""ocr_reader.py — Đọc PDF: ưu tiên text layer PyMuPDF, fallback OCR LlamaParse.

Quy tắc (theo SPEC_buoi_05.md):
- Ưu tiên lấy text layer trực tiếp từ PyMuPDF cho từng trang.
- Nếu BẤT KỲ trang nào lỗi (font/encoding/ký tự lạ/rỗng), chuyển sang OCR
  TOÀN BỘ file bằng LlamaParse (không chỉ riêng trang lỗi).
- Lỗi một trang không được làm dừng job.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pymupdf
from llama_ocr import OcrUnavailableError, ocr_pdf_via_llamaparse
from text_utils import detect_page_error, normalize_nfc


@dataclass
class PageRecord:
    page: int  # 1-based
    text: str
    ocr_used: bool
    language: str = "vi"
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReadResult:
    source: str
    pages: list[PageRecord]
    ocr_fallback_triggered: bool
    global_warnings: list[str] = field(default_factory=list)


def _read_pymupdf_pages(pdf_path: str) -> list[tuple[int, str, list[str]]]:
    """Trả về [(page_1_based, text, error_reasons)]. Lỗi 1 trang không dừng job."""
    results: list[tuple[int, str, list[str]]] = []
    doc = pymupdf.open(pdf_path)
    try:
        for i in range(doc.page_count):
            page_num = i + 1
            try:
                text = doc[i].get_text()
            except Exception as exc:  # noqa: BLE001 - lỗi 1 trang không dừng job
                results.append((page_num, "", [f"lỗi đọc PyMuPDF: {exc}"]))
                continue
            is_error, reasons = detect_page_error(text)
            results.append((page_num, text, reasons if is_error else []))
    finally:
        doc.close()
    return results


def read_pdf(pdf_path: str, source_name: str) -> ReadResult:
    """Luồng đọc chính: PyMuPDF trước, OCR toàn file qua LlamaParse nếu có trang lỗi."""
    pymupdf_pages = _read_pymupdf_pages(pdf_path)
    error_pages = [(p, reasons) for p, _, reasons in pymupdf_pages if reasons]

    if not error_pages:
        pages = [
            PageRecord(page=p, text=normalize_nfc(t), ocr_used=False)
            for p, t, _ in pymupdf_pages
        ]
        return ReadResult(source=source_name, pages=pages, ocr_fallback_triggered=False)

    global_warnings = [
        f"Phát hiện {len(error_pages)}/{len(pymupdf_pages)} trang có dấu hiệu lỗi "
        "text layer — chuyển sang OCR toàn bộ file bằng LlamaParse."
    ]
    for p, reasons in error_pages:
        global_warnings.append(f"Trang {p}: {'; '.join(reasons)}")

    def _fallback_to_pymupdf(extra_warning: str) -> ReadResult:
        global_warnings.append(extra_warning)
        pages = [
            PageRecord(page=p, text=normalize_nfc(t), ocr_used=False, warnings=reasons)
            for p, t, reasons in pymupdf_pages
        ]
        return ReadResult(
            source=source_name,
            pages=pages,
            ocr_fallback_triggered=False,
            global_warnings=global_warnings,
        )

    try:
        ocr_pages = asyncio.run(ocr_pdf_via_llamaparse(pdf_path))
    except OcrUnavailableError as exc:
        return _fallback_to_pymupdf(
            f"OCR fallback thất bại: {exc}. Dùng lại text PyMuPDF gốc (có thể còn lỗi)."
        )

    if not ocr_pages:
        return _fallback_to_pymupdf(
            "OCR trả về rỗng — dùng lại text PyMuPDF gốc (có thể còn lỗi)."
        )

    pages = [
        PageRecord(page=op.page, text=normalize_nfc(op.text), ocr_used=True) for op in ocr_pages
    ]
    return ReadResult(
        source=source_name,
        pages=pages,
        ocr_fallback_triggered=True,
        global_warnings=global_warnings,
    )
