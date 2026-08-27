"""
BUOI 19 - Dual Provider LLM Dispatcher.

Cung cap DUY NHAT mot ham `call_llm(prompt)` de 4 core engine (UC1
internal_lookup, UC2 compliance_gap, UC3 compliance_checker, UC4
audit_checklist_gen) dung chung, thay vi tung file tu goi thang
`google.genai`. Ham nay CHI doi noi goi model (Ollama local / Gemini cloud)
tuy theo bien moi truong LLM_PROVIDER - KHONG thay doi bat ky logic nghiep vu
nao khac (RBAC, regex nguong so, NEEDS_HUMAN_REVIEW, citation that) da duoc
kiem chung o Buoi 17/18.

LLM_PROVIDER=ollama (mac dinh)  -> Local SLM Qwen3:0.6b qua Ollama REST API,
                                    HOAN TOAN OFFLINE, du lieu khong roi mang
                                    cuc bo.
LLM_PROVIDER=gemini             -> Cloud Gemini (tuy chon/fallback, giu lai
                                    tu Buoi 17/18 de so sanh/doi chieu).

Tra ve: chuoi van ban tho (str) giong het `resp.text` cua Gemini truoc day,
de cac engine KHONG can sua logic json.loads()/regex strip fence da co. Tra
ve None neu that bai o bat ky buoc nao -> caller tu fallback ve rule-based/
extractive (nguyen tac "khong tu bia" xuyen suot 3 buoi).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ollama_adapter import OllamaClient  # noqa: E402

_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def get_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "ollama").strip().lower()


def call_llm(prompt: str, temperature: float = 0.2, format_json: bool = True) -> str | None:
    """Dispatch theo LLM_PROVIDER. format_json=True mac dinh vi ca 4 engine
    UC1-UC4 deu can JSON hop le tu LLM (hoac van ban tu do voi UC1)."""
    provider = get_provider()
    if provider == "gemini":
        return _call_gemini(prompt)
    if provider == "ollama":
        return _call_ollama(prompt, temperature=temperature, format_json=format_json)
    print(f"[CANH BAO] LLM_PROVIDER='{provider}' khong hop le (chi ho tro 'ollama'/'gemini'). "
          "Coi nhu khong co LLM.", file=sys.stderr)
    return None


def _call_ollama(prompt: str, temperature: float, format_json: bool) -> str | None:
    client = OllamaClient()
    return client.generate(prompt, format_json=format_json, temperature=temperature)


def _call_gemini(prompt: str) -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        model = os.environ.get("LLM_MODEL", "gemini-3.6-flash")
        resp = client.models.generate_content(model=model, contents=prompt)
        return (resp.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        print(f"[CANH BAO] Goi Gemini that bai ({type(exc).__name__}: {exc}). "
              "Fallback ve rule-based/extractive.", file=sys.stderr)
        return None


def main() -> None:
    provider = get_provider()
    print(f"LLM_PROVIDER hien tai: {provider}")
    result = call_llm("Xin chào, bạn có hoạt động không? Trả lời 1 câu ngắn.", format_json=False)
    print(f"Ket qua goi thu: {'CO PHAN HOI' if result else 'KHONG CO PHAN HOI (offline/loi - binh thuong neu chua bat Ollama/chua co GEMINI_API_KEY)'}")
    if result:
        print(f"Noi dung: {result[:200]}")


if __name__ == "__main__":
    main()
