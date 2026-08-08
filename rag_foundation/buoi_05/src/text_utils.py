"""text_utils.py — Chuẩn hoá Unicode NFC và heuristic phát hiện lỗi text layer.

Heuristic ở đây là bản đơn giản cho mục đích minh hoạ (demo), KHÔNG phải bộ
phát hiện lỗi font/encoding hoàn chỉnh cho môi trường production.
"""

from __future__ import annotations

import re
import unicodedata

_VN_DIACRITIC_RE = re.compile(
    "[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
    "ùúụủũưừứựửữỳýỵỷỹđ"
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠ"
    "ÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
)
_CONTROL_OR_REPLACEMENT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f�]")

MIN_LEN_FOR_DIACRITIC_CHECK = 200
MIN_DIACRITIC_RATIO = 0.01  # tỷ lệ ký tự có dấu tối thiểu kỳ vọng trong văn bản tiếng Việt dài
MAX_CONTROL_CHAR_RATIO = 0.01


def normalize_nfc(text: str) -> str:
    """Chuẩn hoá chuỗi về dạng Unicode NFC."""
    return unicodedata.normalize("NFC", text or "")


def detect_page_error(text: str) -> tuple[bool, list[str]]:
    """
    Kiểm tra heuristic xem text trích từ PyMuPDF có đáng ngờ (lỗi font/encoding/
    ký tự lạ/rỗng) hay không.

    Trả về (is_error, reasons) — reasons là danh sách mô tả bằng tiếng Việt để
    ghi log cảnh báo.
    """
    reasons: list[str] = []
    stripped = (text or "").strip()

    if not stripped:
        reasons.append("trang rỗng (không trích được ký tự có nghĩa)")
        return True, reasons

    control_ratio = len(_CONTROL_OR_REPLACEMENT_RE.findall(text)) / max(len(text), 1)
    if control_ratio > MAX_CONTROL_CHAR_RATIO:
        reasons.append(
            f"tỷ lệ ký tự điều khiển/ký tự lạ cao bất thường ({control_ratio:.1%})"
        )

    if len(stripped) >= MIN_LEN_FOR_DIACRITIC_CHECK:
        diacritic_count = len(_VN_DIACRITIC_RE.findall(stripped))
        diacritic_ratio = diacritic_count / len(stripped)
        if diacritic_ratio < MIN_DIACRITIC_RATIO:
            reasons.append(
                "gần như không có dấu tiếng Việt trong văn bản dài — nghi ngờ lỗi "
                f"font/encoding (tỷ lệ ký tự có dấu chỉ {diacritic_ratio:.2%})"
            )

    return (len(reasons) > 0), reasons
