"""
Kiem tra nhanh GEMINI_API_KEY — chi goi 1 lan, chay trong vai giay.
Chay: python test_gemini.py
Khong in khoa API ra man hinh.
"""
import os
import sys
from dotenv import load_dotenv

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))

key = os.getenv("GEMINI_API_KEY", "")
model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

print("=" * 58)
print("KIEM TRA GEMINI API")
print("=" * 58)

if not key.strip():
    print("[FAIL] Khong tim thay GEMINI_API_KEY trong .env")
    sys.exit(1)

print("Do dai key : %d ky tu" % len(key))
print("Dang key   : %s...%s" % (key[:6], key[-4:]))
print("Model      : %s" % model)
print("-" * 58)

try:
    from google import genai
except ImportError:
    print("[FAIL] Chua cai google-genai trong moi truong Python nay")
    sys.exit(1)

try:
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=model,
        contents="Tra loi duy nhat hai chu: OK",
    )
    print("[PASS] Goi Gemini THANH CONG")
    print("Phan hoi tu Gemini: %s" % (resp.text or "").strip()[:120])
    print("\n=> API da dung. Chay tiep:  python step3_gemini_run.py")
except Exception as e:
    msg = str(e)
    print("[FAIL] Goi Gemini that bai")
    print("Loai loi : %s" % type(e).__name__)
    print("Chi tiet : %s" % msg[:400])
    print("-" * 58)
    if "dunning" in msg.lower() or "PERMISSION_DENIED" in msg:
        print("CHAN DOAN: project Google Cloud gan voi khoa nay dang bi khoa")
        print("           quyen goi API vi ly do THANH TOAN.")
        print("HUONG XU LY: tao khoa moi tai https://aistudio.google.com/apikey")
        print("             (chon tao trong mot project MOI), roi thay vao .env")
    elif "API_KEY_INVALID" in msg or "API key not valid" in msg:
        print("CHAN DOAN: khoa API khong hop le (sai hoac da bi xoa).")
    elif "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        print("CHAN DOAN: het han muc (quota). Doi hoac doi sang khoa khac.")
    elif "NOT_FOUND" in msg or "404" in msg:
        print("CHAN DOAN: ten model khong ton tai. Thu GEMINI_MODEL=gemini-2.5-flash")
    sys.exit(1)
