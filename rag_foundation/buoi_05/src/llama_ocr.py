"""llama_ocr.py — Gọi LlamaParse (llama_cloud) để OCR toàn bộ file PDF.

LƯU Ý BẢO MẬT: module này chỉ SỬ DỤNG giá trị LLAMA_CLOUD_API_KEY để khởi tạo
client. Tuyệt đối không in, log, hay trả giá trị key ra ngoài dưới bất kỳ
hình thức nào (kể cả một phần key trong thông báo lỗi).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class OcrUnavailableError(RuntimeError):
    """Không thể chạy OCR (thiếu key hợp lệ, lỗi kết nối, lỗi API, ...)."""


@dataclass
class OcrPageResult:
    page: int  # 1-based
    text: str


def _get_valid_api_key() -> str | None:
    key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not key:
        return None
    key = key.strip()
    if not key or key == "KEY CỦA BẠN":
        return None
    return key


async def ocr_pdf_via_llamaparse(pdf_path: str) -> list[OcrPageResult]:
    """
    Gửi toàn bộ PDF lên LlamaParse (tier='agentic') và trả về text theo từng trang.

    LlamaParse tự xử lý việc render trang sang ảnh khi cần ở phía server —
    code này chỉ cần truyền file PDF gốc, không cần tự rasterize từng trang.

    Raises:
        OcrUnavailableError: nếu thiếu API key hợp lệ hoặc lời gọi API thất bại.
    """
    api_key = _get_valid_api_key()
    if api_key is None:
        raise OcrUnavailableError(
            "Thiếu LLAMA_CLOUD_API_KEY hợp lệ trong .env — không thể chạy OCR fallback."
        )

    try:
        from llama_cloud import AsyncLlamaCloud
    except ImportError as exc:
        raise OcrUnavailableError(f"Chưa cài package llama_cloud: {exc}") from exc

    client = AsyncLlamaCloud(api_key=api_key)
    try:
        file_obj = await client.files.create(file=pdf_path, purpose="parse")
        result = await client.parsing.parse(
            file_id=file_obj.id,
            tier="agentic",
            version="latest",
            expand=["markdown"],
        )
    except Exception as exc:  # noqa: BLE001 - bọc mọi lỗi API thành lỗi nghiệp vụ rõ ràng
        raise OcrUnavailableError(f"Gọi LlamaParse thất bại: {exc}") from exc

    pages = getattr(getattr(result, "markdown", None), "pages", None) or []
    return [OcrPageResult(page=i + 1, text=(p.markdown or "")) for i, p in enumerate(pages)]
