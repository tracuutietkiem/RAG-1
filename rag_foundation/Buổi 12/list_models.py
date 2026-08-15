"""
Liet ke cac model Gemini ma API key hien tai truy cap duoc.
Chay: python list_models.py
Chi goi 1 lan, khong ton quota sinh noi dung.
"""
import os
import sys
from dotenv import load_dotenv

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))
key = os.getenv("GEMINI_API_KEY", "")

if not key.strip():
    print("[FAIL] Khong tim thay GEMINI_API_KEY trong .env")
    sys.exit(1)

from google import genai

client = genai.Client(api_key=key)

print("=" * 74)
print("CAC MODEL KHA DUNG VOI API KEY NAY")
print("=" * 74)

rows = []
try:
    for m in client.models.list():
        name = (m.name or "").replace("models/", "")
        actions = getattr(m, "supported_actions", None) or []
        if actions and "generateContent" not in actions:
            continue
        rows.append((name, getattr(m, "display_name", "") or ""))
except Exception as e:
    print("[FAIL] Khong liet ke duoc model: %s" % str(e)[:300])
    sys.exit(1)

if not rows:
    print("Khong co model nao ho tro generateContent.")
    sys.exit(1)

rows.sort()
print("%-42s %s" % ("TEN MODEL (dat vao GEMINI_MODEL)", "MO TA"))
print("-" * 74)
for name, disp in rows:
    print("%-42s %s" % (name, disp[:30]))

print("-" * 74)
print("Tong: %d model" % len(rows))

flash = [n for n, _ in rows if "flash" in n and "thinking" not in n and "image" not in n]
if flash:
    print("\nGoi y (nen chon ban 'flash' on dinh, khong phai preview/exp):")
    for n in flash[:12]:
        print("   %s" % n)
print("\nSau khi chon, sua dong GEMINI_MODEL= trong file .env roi chay test_gemini.py")
