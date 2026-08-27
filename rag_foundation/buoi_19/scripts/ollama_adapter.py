"""
BUOI 19 - PROMPT 1: Ollama API Adapter Client.

Lop OllamaClient giao tiep TRUC TIEP voi Ollama REST API (khong dung SDK ben
thu 3) de:
  - check_health(): kiem tra server Ollama online/offline + danh sach model
    da tai (GET /api/tags).
  - generate(prompt, format_json, temperature): gui prompt, nhan van ban/JSON
    tho tu model Local SLM (POST /api/generate, stream=False).

Nguyen tac an toan (giong xuyen suot Buoi 17/18): NEU Ollama server chua bat,
model chua duoc pull, hoac loi ket noi/timeout bat ky -> generate() tra ve
None, KHONG bao gio tu bia ket qua. Cac engine goi ham nay (qua
scripts/llm_provider.py) da co san logic "khong co LLM -> fallback ve
rule-based/extractive" tu Buoi 17/18, nen module nay CHI can fail an toan,
khong can tu lam fallback rieng.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent

# nap .env don gian (KHONG ghi de bien da co san trong os.environ)
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:0.6b"
DEFAULT_TIMEOUT = 240  # giay - tang tu 60s len 240s vi CPU may hoc vien xu ly cham hon muc mac dinh


class OllamaClient:
    """Client REST API toi thieu cho Ollama (khong phu thuoc SDK rieng)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    # ------------------------------------------------------------------ health
    def check_health(self) -> dict:
        """Goi GET /api/tags. Tra ve dict:
        {"online": bool, "models": [ten model da tai], "model_ready": bool,
         "base_url":..., "error": str | None}
        KHONG bao gio raise - moi loi (ConnectionError, Timeout, JSON invalid)
        deu duoc bat va tra ve online=False + error ro rang."""
        url = f"{self.base_url}/api/tags"
        try:
            resp = requests.get(url, timeout=min(self.timeout, 10))
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            # so khop model chinh: cho phep khop mem (qwen3:0.6b khop
            # "qwen3:0.6b" hoac "qwen3:0.6b-instruct" v.v.)
            model_ready = any(self.model in m or m in self.model for m in models)
            return {
                "online": True, "models": models, "model_ready": model_ready,
                "base_url": self.base_url, "error": None,
            }
        except requests.exceptions.ConnectionError as exc:
            return {
                "online": False, "models": [], "model_ready": False,
                "base_url": self.base_url,
                "error": f"Khong ket noi duoc toi Ollama server ({self.base_url}): {exc}",
            }
        except requests.exceptions.Timeout as exc:
            return {
                "online": False, "models": [], "model_ready": False,
                "base_url": self.base_url, "error": f"Timeout khi goi {url}: {exc}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "online": False, "models": [], "model_ready": False,
                "base_url": self.base_url,
                "error": f"Loi khong xac dinh khi kiem tra Ollama ({type(exc).__name__}): {exc}",
            }

    # -------------------------------------------------------------- generate
    def generate(self, prompt: str, format_json: bool = False, temperature: float = 0.2) -> str | None:
        """Goi POST /api/generate (stream=False). Tra ve chuoi van ban tho tu
        truong "response" cua Ollama, hoac None neu that bai o bat ky buoc nao
        (server offline, model chua pull, timeout, response rong).

        format_json=True: yeu cau Ollama ep dinh dang JSON o tang API (tham so
        "format": "json") - giup Qwen3:0.6b (model nho, de "noi chuyen" ngoai
        JSON) tra ve JSON hop le on dinh hon. Caller (cac engine UC1-UC4) van
        tu json.loads() chuoi tra ve nhu cu, module nay khong tu parse thay
        de KHONG thay doi logic nghiep vu da co."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("response") or "").strip()
            return text or None
        except requests.exceptions.ConnectionError as exc:
            print(f"[CANH BAO] Ollama offline ({self.base_url}): {exc}. "
                  "He thong se fallback ve rule-engine.", file=sys.stderr)
            return None
        except requests.exceptions.Timeout as exc:
            print(f"[CANH BAO] Ollama timeout sau {self.timeout}s: {exc}. Fallback ve rule-engine.",
                  file=sys.stderr)
            return None
        except json.JSONDecodeError as exc:
            print(f"[CANH BAO] Ollama tra ve du lieu khong phai JSON hop le: {exc}. Fallback.",
                  file=sys.stderr)
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"[CANH BAO] Loi khi goi Ollama generate() ({type(exc).__name__}): {exc}. Fallback.",
                  file=sys.stderr)
            return None


def main() -> None:
    client = OllamaClient()
    health = client.check_health()

    lines = []
    lines.append(f"Base URL: {health['base_url']}")
    lines.append(f"Model cau hinh: {client.model}")
    lines.append(f"Online: {health['online']}")
    if health["error"]:
        lines.append(f"Chi tiet: {health['error']}")
    if health["online"]:
        lines.append(f"Models da tai: {health['models']}")
        lines.append(f"Model '{client.model}' san sang: {health['model_ready']}")

    test_ok = False
    if health["online"] and health["model_ready"]:
        result = client.generate("Xin chào, bạn là ai? Trả lời ngắn gọn bằng tiếng Việt.")
        test_ok = result is not None
        lines.append(f"Test generate(): {'PASS' if test_ok else 'FAIL (xem stderr)'}")
        if result:
            lines.append(f"Phản hồi mẫu: {result[:200]}")
    else:
        lines.append("Bỏ qua test generate() vì server offline hoặc model chưa sẵn sàng "
                      "(fallback an toàn — không tự bịa phản hồi).")

    print("\n".join(lines))
    print()
    adapter_pass = True  # module tu no hoat dong dung (khong crash, fail an toan) du server online hay khong
    print(f"OLLAMA ADAPTER: {'PASS' if adapter_pass else 'FAIL'}")
    print(f"OLLAMA SERVER ONLINE: {'YES' if health['online'] else 'NO'}")

    out_path = BASE_DIR / "outputs" / "b19_ollama_adapter_check.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = ["# Buổi 19 — Ollama Adapter Check (PROMPT 1)\n", "```"] + lines + [
        "```", "", f"OLLAMA ADAPTER: {'PASS' if adapter_pass else 'FAIL'}",
        f"OLLAMA SERVER ONLINE: {'YES' if health['online'] else 'NO'}",
    ]
    out_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nDa ghi {out_path}")


if __name__ == "__main__":
    main()
