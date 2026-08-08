"""
check_ocr_env.py — Kiểm tra môi trường OCR/RAG cho Buổi 5.

Kiểm tra: Python, PyMuPDF, Pillow, llama_cloud, Pydantic, Streamlit, python-dotenv.
In bảng PASS/FAIL. KHÔNG in giá trị secret (API key) dưới bất kỳ hình thức nào.

Cách chạy:
    python src/check_ocr_env.py
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass

MIN_PYTHON = (3, 9)

# (tên hiển thị, tên module import, gói pip để cài nếu thiếu)
REQUIRED_PACKAGES: list[tuple[str, str, str]] = [
    ("PyMuPDF", "pymupdf", "pymupdf"),
    ("Pillow", "PIL", "pillow"),
    ("llama_cloud", "llama_cloud", "llama_cloud"),
    ("Pydantic", "pydantic", "pydantic"),
    ("Streamlit", "streamlit", "streamlit"),
    ("python-dotenv", "dotenv", "python-dotenv"),
]


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "FAIL"
    detail: str


def check_python_version() -> CheckResult:
    ok = sys.version_info[:2] >= MIN_PYTHON
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if ok:
        return CheckResult("Python", "PASS", f"v{ver} (>= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")
    return CheckResult("Python", "FAIL", f"v{ver} — cần >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")


def check_package(display_name: str, module_name: str) -> CheckResult:
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", None)
        if version is None and module_name == "pymupdf":
            version = getattr(mod, "VersionBind", "?")
        detail = f"đã cài (v{version})" if version else "đã cài"
        return CheckResult(display_name, "PASS", detail)
    except ImportError as exc:
        return CheckResult(display_name, "FAIL", f"chưa cài — lỗi: {exc}")


def check_env_file() -> CheckResult:
    """Kiểm tra sự tồn tại của biến LLAMA_CLOUD_API_KEY, KHÔNG in giá trị."""
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    key = os.getenv("LLAMA_CLOUD_API_KEY")
    if key and key.strip() and key.strip() != "KEY CỦA BẠN":
        return CheckResult("LLAMA_CLOUD_API_KEY", "PASS", "đã cấu hình (giá trị được giữ kín)")
    return CheckResult(
        "LLAMA_CLOUD_API_KEY", "FAIL", "chưa cấu hình hoặc còn để placeholder trong .env"
    )


def print_table(results: list[CheckResult]) -> None:
    name_w = max(len(r.name) for r in results) + 2
    status_w = 6
    print(f"{'Thành phần':<{name_w}}{'Kết quả':<{status_w}}Chi tiết")
    print("-" * (name_w + status_w + 40))
    for r in results:
        print(f"{r.name:<{name_w}}{r.status:<{status_w}}{r.detail}")


def suggest_fix(results: list[CheckResult]) -> None:
    fails = [r for r in results if r.status == "FAIL"]
    if not fails:
        print("\nTất cả kiểm tra đều PASS. Môi trường sẵn sàng cho Buổi 5.")
        return

    print("\nCác bước khắc phục đề xuất (KHÔNG tự động cài khi chưa được đồng ý):")
    pip_map = {name: pip for name, _, pip in REQUIRED_PACKAGES}
    for r in fails:
        if r.name == "Python":
            print(f"- Nâng cấp Python lên >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}.")
        elif r.name in pip_map:
            print(f"- Cài đặt: pip install {pip_map[r.name]} --break-system-packages")
        elif r.name == "LLAMA_CLOUD_API_KEY":
            print(
                "- Mở file src/.env, dán API key LlamaCloud thật vào biến "
                "LLAMA_CLOUD_API_KEY (thay cho placeholder 'KEY CỦA BẠN')."
            )


def main() -> int:
    results = [check_python_version()]
    for display_name, module_name, _ in REQUIRED_PACKAGES:
        results.append(check_package(display_name, module_name))
    results.append(check_env_file())

    print_table(results)
    suggest_fix(results)

    return 0 if all(r.status == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
