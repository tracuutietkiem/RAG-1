"""
BUOI 19 - PROMPT SETUP: Kiem tra moi truong Docker/Ollama & du lieu.

Xuat: outputs/b19_setup_report.md
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT = BASE_DIR / "outputs" / "b19_setup_report.md"

_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def _run_version(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, (result.stderr or result.stdout).strip()
    except FileNotFoundError:
        return False, f"Không tìm thấy lệnh: {' '.join(cmd)}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Lỗi: {exc}"


def main() -> None:
    lines = ["# Buổi 19 — Setup Check Report (PROMPT SETUP)\n"]

    docker_ok, docker_ver = _run_version(["docker", "--version"])
    compose_ok, compose_ver = _run_version(["docker", "compose", "version"])
    docker_ready = docker_ok and compose_ok
    lines.append("## Docker\n")
    lines.append(f"- `docker --version`: {'✅' if docker_ok else '❌'} {docker_ver}")
    lines.append(f"- `docker compose version`: {'✅' if compose_ok else '❌'} {compose_ver}\n")

    internal_csv = BASE_DIR / os.environ.get("SOURCE_INTERNAL_POLICY_CSV", "../buoi_17/data/agribank_internal_policies.csv")
    combined_csv = BASE_DIR / os.environ.get("SOURCE_COMBINED_SECURE_CSV", "../buoi_17/data/chunks_combined_secure.csv")
    data_ready = internal_csv.exists() and combined_csv.exists()
    lines.append("## Dữ liệu nguồn (read-only, tái sử dụng từ buoi_17/data)\n")
    lines.append(f"- `{internal_csv}`: {'✅ tồn tại' if internal_csv.exists() else '❌ THIẾU'}")
    lines.append(f"- `{combined_csv}`: {'✅ tồn tại' if combined_csv.exists() else '❌ THIẾU'}\n")

    scripts_dir = BASE_DIR / "scripts"
    outputs_dir = BASE_DIR / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    dirs_ready = scripts_dir.is_dir() and outputs_dir.is_dir()
    lines.append("## Thư mục dự án\n")
    lines.append(f"- `scripts/`: {'✅' if scripts_dir.is_dir() else '❌'}")
    lines.append(f"- `outputs/`: {'✅' if outputs_dir.is_dir() else '❌'}\n")

    provider_ok = os.environ.get("LLM_PROVIDER", "").strip().lower() == "ollama"
    model_ok = os.environ.get("OLLAMA_MODEL", "").strip() == "qwen3:0.6b"
    env_ready = provider_ok and model_ok
    lines.append("## Cấu hình .env\n")
    lines.append(f"- `LLM_PROVIDER=ollama`: {'✅' if provider_ok else '❌'} (hiện tại: `{os.environ.get('LLM_PROVIDER')}`)")
    lines.append(f"- `OLLAMA_MODEL=qwen3:0.6b`: {'✅' if model_ok else '❌'} (hiện tại: `{os.environ.get('OLLAMA_MODEL')}`)")
    gemini_key_present = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    lines.append(f"- `GEMINI_API_KEY` (fallback tuỳ chọn): {'có cấu hình' if gemini_key_present else 'để trống'}\n")

    lines.append("## Kết luận\n")
    lines.append(f"DOCKER READY: {'YES' if docker_ready else 'NO'}")
    lines.append(f"DATA READY: {'YES' if data_ready else 'NO'}")
    lines.append(f"ENV CONFIG READY: {'YES' if env_ready else 'NO'}")

    if not docker_ready:
        lines.append("")
        lines.append(
            "**Lưu ý**: nếu `docker --version`/`docker compose version` FAIL, cần cài Docker Desktop "
            "(Windows/Mac) hoặc Docker Engine + plugin compose (Linux) trước khi tiếp tục PROMPT 4."
        )

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print("\n".join(lines[-4:]))

    if not (docker_ready and data_ready and env_ready):
        sys.exit(1)


if __name__ == "__main__":
    main()
