"""
BƯỚC 3 (bản chạy trên máy người dùng) — Entity Extraction & Metadata Enrichment bằng GEMINI THẬT

Chỉ dùng thư viện chuẩn của Python + google-genai + python-dotenv
(KHÔNG cần pandas) để tái sử dụng venv sẵn có của buổi 11.

Input : ner_kb/cleaned_documents.csv
Output: ner_kb/extracted_entities_gemini.csv
        ner_kb/enriched_metadata_gemini.csv
        loi_buoc3_gemini.txt (nếu có lỗi)

Nguyên tắc: ưu tiên metadata gốc; không có evidence -> không tạo entity;
lỗi 1 document không làm dừng batch; không in GEMINI_API_KEY.
"""
import os
import re
import csv
import sys
import json
import time
import unicodedata

csv.field_size_limit(min(2**31 - 1, sys.maxsize))

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE = os.path.dirname(os.path.abspath(__file__))
IN_PATH = os.path.join(BASE, "ner_kb", "cleaned_documents.csv")
OUT_ENT = os.path.join(BASE, "ner_kb", "extracted_entities_gemini.csv")
OUT_ENR = os.path.join(BASE, "ner_kb", "enriched_metadata_gemini.csv")
ERR_LOG = os.path.join(BASE, "loi_buoc3_gemini.txt")

load_dotenv(os.path.join(BASE, ".env"))
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

HEAD_CHARS, TAIL_CHARS = 9000, 4000
UNCLEAR = {"", "nan", "none", "null", "chưa phân loại"}

# Nhip goi va co che thu lai (key free-tier thuong gioi han ~10-15 luot/phut)
SLEEP_BETWEEN = float(os.getenv("GEMINI_SLEEP", "5"))

# Danh sach model du phong. Moi model co HAN MUC RIENG -> het quota model nay
# thi tu dong chuyen sang model ke tiep. Uu tien ban flash-lite (han muc cao hon).
_DEFAULT_CHAIN = ("gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-flash-lite-latest,"
                  "gemini-3.5-flash,gemini-3.6-flash,gemini-3.7-flash")
MODEL_CHAIN = [m.strip() for m in os.getenv("GEMINI_MODELS", _DEFAULT_CHAIN).split(",") if m.strip()]
MAX_RETRY = int(os.getenv("GEMINI_MAX_RETRY", "3"))
CACHE_DIR = os.path.join(BASE, "ner_kb", "_step3_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

RETRYABLE = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE",
             "500", "INTERNAL", "DEADLINE_EXCEEDED", "504")


def is_retryable(msg):
    return any(t in msg for t in RETRYABLE)


def is_quota_error(msg):
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def is_model_unavailable(msg):
    return "404" in msg or "NOT_FOUND" in msg or "no longer available" in msg


def server_retry_delay(msg):
    """Google tra ve thoi gian cho chinh xac trong loi 429 -> dung dung con so do."""
    m = re.search(r"[Pp]lease retry in ([0-9.]+)s", msg)
    if not m:
        m = re.search(r"'retryDelay':\s*'([0-9.]+)s'", msg)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def call_with_retry(fn, tag):
    """Goi Gemini, tu dong thu lai voi thoi gian cho tang dan khi bi 429/503."""
    delay = 12.0
    last = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            msg = str(e)
            if attempt < MAX_RETRY and is_retryable(msg):
                hinted = server_retry_delay(msg)
                wait = (hinted + 2.0) if hinted else delay
                src = "may chu de nghi" if hinted else "tang dan"
                print("      [retry %d/%d] %s bi gioi han, cho %.0fs (%s)..."
                      % (attempt, MAX_RETRY - 1, tag, wait, src))
                time.sleep(wait)
                delay *= 2
                continue
            raise
    raise last


def is_unclear(v):
    return v is None or str(v).strip().lower() in UNCLEAR


def excerpt_of(text):
    if not text:
        return ""
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text
    return text[:HEAD_CHARS] + "\n\n[... đã lược bớt phần giữa văn bản ...]\n\n" + text[-TAIL_CHARS:]


def norm_ws(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s))).strip().lower()


def grounded(evidence, full_text):
    """Evidence phải thực sự xuất hiện trong văn bản gốc (chống hallucination)."""
    if not evidence:
        return False
    ev, doc = norm_ws(evidence), norm_ws(full_text)
    if not ev:
        return False
    if ev in doc:
        return True
    if len(ev) > 20:
        return ev[: max(20, int(len(ev) * 0.7))] in doc
    return False


PROMPT = """Bạn là chuyên gia phân tích văn bản pháp luật ngân hàng Việt Nam.
Đọc đoạn trích dưới đây và trích xuất CHÍNH XÁC các thông tin sau, CHỈ dựa trên nội dung
có trong đoạn trích. TUYỆT ĐỐI KHÔNG suy diễn hay bịa thông tin không có bằng chứng.

Metadata gốc đã có (đối chiếu, KHÔNG ghi đè nếu đã rõ):
- co_quan_ban_hanh: {mcq}
- nguoi_ky: {mnk}
- linh_vuc: {mlv}

Nhiệm vụ:
1. co_quan: Cơ quan ban hành. Nếu đoạn trích xác nhận đúng metadata gốc thì trả về entity đó
   kèm evidence trích nguyên văn, matches_metadata=true. Nếu KHÁC metadata gốc thì trả về giá trị
   theo văn bản với matches_metadata=false.
2. nguoi_ky: Người ký (thường ở cuối văn bản, dưới chức danh như "TL. THỐNG ĐỐC",
   "KT. BỘ TRƯỞNG", "CHỦ TỊCH QUỐC HỘI"...). Xử lý tương tự mục 1.
3. doi_tuong_ap_dung: Liệt kê TỪNG đối tượng chịu sự điều chỉnh RIÊNG BIỆT (mỗi đối tượng một
   entity, không gộp thành một câu dài), thường ở mục "Đối tượng áp dụng". Nếu văn bản không có
   mục này rõ ràng trong đoạn trích, trả về mảng rỗng.
4. linh_vuc: CHỈ đề xuất nếu metadata gốc đang thiếu/rỗng/"Chưa phân loại". Nếu metadata gốc đã rõ,
   trả về mảng rỗng. Ví dụ lĩnh vực: Tín dụng, Kiểm toán, Bảo hiểm, Chứng khoán, Quản lý ngoại hối,
   Phát hành và kho quỹ, Thanh tra giám sát ngân hàng.

Mỗi entity BẮT BUỘC có: entity, evidence (trích NGUYÊN VĂN từ đoạn trích, không viết lại),
confidence (0.0-1.0, phản ánh trung thực; KHÔNG đặt 1.0 cho tất cả; nêu tường minh >= 0.85;
suy luận gián tiếp thì thấp hơn).

Nếu không có bằng chứng cho mục nào, trả về mảng rỗng [] cho mục đó.
Chỉ trả về JSON đúng schema, không giải thích, không markdown.

--- ĐOẠN TRÍCH (id={did}, số hiệu={sky}) ---
{ex}
--- HẾT ĐOẠN TRÍCH ---
"""

ENT_ITEM = {
    "type": "OBJECT",
    "properties": {
        "entity": {"type": "STRING"},
        "evidence": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "matches_metadata": {"type": "BOOLEAN"},
    },
    "required": ["entity", "evidence", "confidence"],
}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "co_quan": {"type": "ARRAY", "items": ENT_ITEM},
        "nguoi_ky": {"type": "ARRAY", "items": ENT_ITEM},
        "doi_tuong_ap_dung": {"type": "ARRAY", "items": ENT_ITEM},
        "linh_vuc": {"type": "ARRAY", "items": ENT_ITEM},
    },
    "required": ["co_quan", "nguoi_ky", "doi_tuong_ap_dung", "linh_vuc"],
}


def main():
    if not API_KEY:
        print("[FAIL] Khong tim thay GEMINI_API_KEY trong .env")
        sys.exit(1)

    with open(IN_PATH, "r", encoding="utf-8", newline="") as f:
        docs = list(csv.DictReader(f))

    print("=" * 66)
    print("BUOC 3 - GEMINI ENTITY EXTRACTION (chay that tren may nguoi dung)")
    print("=" * 66)
    print("Input: %d document" % len(docs))
    print("Chuoi model du phong: %s" % " -> ".join(MODEL_CHAIN))
    print("Nhip goi: %.0fs/document (~%.1f luot/phut) | thu lai toi da: %d lan"
          % (SLEEP_BETWEEN, 60.0 / SLEEP_BETWEEN, MAX_RETRY - 1))
    print("Uoc tinh: ~%.0f phut cho %d document" % (len(docs) * SLEEP_BETWEEN / 60.0, len(docs)))
    cached = len([f for f in os.listdir(CACHE_DIR) if f.endswith(".json")])
    if cached:
        print("Da co cache cho %d document -> chi goi API cho phan con thieu" % cached)

    client = genai.Client(api_key=API_KEY)

    state = {"idx": 0}          # model dang dung trong MODEL_CHAIN
    models_used = {}            # thong ke model nao xu ly bao nhieu document

    def generate(prompt, tag):
        """Goi Gemini; het quota model hien tai -> tu chuyen sang model ke tiep."""
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCHEMA, temperature=0.1)
        last = None
        while state["idx"] < len(MODEL_CHAIN):
            model = MODEL_CHAIN[state["idx"]]
            try:
                r = call_with_retry(
                    lambda: client.models.generate_content(
                        model=model, contents=prompt, config=cfg), tag)
                models_used[model] = models_used.get(model, 0) + 1
                return r
            except Exception as e:
                last = e
                msg = str(e)
                if is_quota_error(msg) or is_model_unavailable(msg):
                    ly_do = "het han muc" if is_quota_error(msg) else "khong dung duoc"
                    state["idx"] += 1
                    if state["idx"] < len(MODEL_CHAIN):
                        print("      >>> Model '%s' %s -> chuyen sang '%s'"
                              % (model, ly_do, MODEL_CHAIN[state["idx"]]))
                        continue
                    print("      >>> Da thu het %d model, deu khong dung duoc"
                          % len(MODEL_CHAIN))
                raise
        raise last

    ent_rows, enr_rows, errors = [], [], []
    n_ok = n_fail = n_filtered = 0

    for i, row in enumerate(docs):
        did = row.get("id", "")
        sky = row.get("so_ky_hieu", "")
        content = row.get("content_clean", "") or ""
        mcq, mnk, mlv = row.get("co_quan_ban_hanh"), row.get("nguoi_ky"), row.get("linh_vuc")

        enr = dict(row)
        enr.pop("content_html", None)
        enr.pop("content_clean", None)
        enr["co_quan_enriched"] = "" if is_unclear(mcq) else mcq
        enr["nguoi_ky_enriched"] = "" if is_unclear(mnk) else mnk
        enr["linh_vuc_enriched"] = "" if is_unclear(mlv) else mlv
        enr["doi_tuong_ap_dung"] = ""
        enr["enrichment_notes"] = ""

        # Entity từ metadata gốc (ưu tiên tuyệt đối)
        for val, etype, col in ((mcq, "CoQuan", "co_quan_ban_hanh"),
                                 (mnk, "NguoiKy", "nguoi_ky"),
                                 (mlv, "LinhVuc", "linh_vuc")):
            if not is_unclear(val):
                ent_rows.append({
                    "entity": str(val).strip(), "entity_type": etype,
                    "source_doc_id": did, "source": "metadata",
                    "method": "metadata_original", "confidence": 1.0,
                    "evidence": "metadata.csv: %s = '%s'" % (col, val),
                })

        parsed = None
        cache_file = os.path.join(CACHE_DIR, "%s.json" % str(did).replace("/", "_"))
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as cf:
                    parsed = json.load(cf)
                n_ok += 1
                print("  [%d/%d] %s - dung lai ket qua da co (cache)" % (i + 1, len(docs), sky))
            except Exception:
                parsed = None

        try:
            if parsed is not None:
                raise StopIteration  # da co cache, bo qua goi API
            resp = generate(PROMPT.format(
                did=did, sky=sky, ex=excerpt_of(content),
                mcq=mcq if not is_unclear(mcq) else "(thieu)",
                mnk=mnk if not is_unclear(mnk) else "(thieu)",
                mlv=mlv if not is_unclear(mlv) else "(thieu - CAN Gemini phan loai)",
            ), sky)
            txt = resp.text
            if not txt or not txt.strip():
                raise ValueError("Gemini tra ve response rong")
            parsed = json.loads(txt)
            with open(cache_file, "w", encoding="utf-8") as cf:
                json.dump(parsed, cf, ensure_ascii=False)
            n_ok += 1
        except StopIteration:
            pass
        except json.JSONDecodeError as e:
            n_fail += 1
            errors.append((did, sky, "invalid_json", str(e)))
        except Exception as e:
            n_fail += 1
            errors.append((did, sky, type(e).__name__, str(e)))

        if parsed is not None:

            def take(key, etype, only_if_meta_unclear, meta_val, enr_col):
                nonlocal n_filtered
                names = []
                for e in (parsed.get(key) or []):
                    ev = e.get("evidence", "")
                    if not grounded(ev, content):
                        n_filtered += 1
                        continue
                    name = str(e.get("entity", "")).strip()
                    if not name:
                        continue
                    matches = e.get("matches_metadata", True)
                    if only_if_meta_unclear and not is_unclear(meta_val) and matches:
                        continue  # metadata gốc đã rõ và Gemini xác nhận trùng -> không tạo entity mới
                    try:
                        conf = float(e.get("confidence", 0.5))
                    except (TypeError, ValueError):
                        conf = 0.5
                    ent_rows.append({
                        "entity": name, "entity_type": etype, "source_doc_id": did,
                        "source": "content_clean", "method": "gemini",
                        "confidence": conf, "evidence": str(ev)[:400],
                    })
                    names.append(name)
                    if only_if_meta_unclear and not is_unclear(meta_val) and not matches:
                        enr["enrichment_notes"] += "[%s] metadata='%s' vs Gemini='%s' - CAN XEM LAI. " % (
                            etype, meta_val, name)
                    if enr_col and is_unclear(meta_val) and not enr[enr_col]:
                        enr[enr_col] = name
                return names

            take("co_quan", "CoQuan", True, mcq, "co_quan_enriched")
            take("nguoi_ky", "NguoiKy", True, mnk, "nguoi_ky_enriched")
            dta = take("doi_tuong_ap_dung", "DoiTuongApDung", False, None, None)
            if dta:
                enr["doi_tuong_ap_dung"] = "; ".join(dta)
            if is_unclear(mlv):
                take("linh_vuc", "LinhVuc", False, mlv, "linh_vuc_enriched")

        enr_rows.append(enr)
        if i + 1 < len(docs) and not os.path.exists(cache_file):
            time.sleep(SLEEP_BETWEEN)
        if (i + 1) % 5 == 0 or (i + 1) == len(docs):
            print("  ... da xu ly %d/%d document" % (i + 1, len(docs)))

    ent_cols = ["entity", "entity_type", "source_doc_id", "source", "method", "confidence", "evidence"]
    with open(OUT_ENT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ent_cols)
        w.writeheader()
        w.writerows(ent_rows)

    enr_cols = list(enr_rows[0].keys()) if enr_rows else []
    with open(OUT_ENR, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=enr_cols)
        w.writeheader()
        w.writerows(enr_rows)

    if errors:
        with open(ERR_LOG, "w", encoding="utf-8") as f:
            f.write("BUOC 3 - Loi khi goi Gemini (%d document)\n%s\n" % (len(errors), "=" * 60))
            for did, sky, et, msg in errors:
                f.write("id=%s  so_ky_hieu=%s  loai_loi=%s\n  message: %s\n\n" % (did, sky, et, msg))
        print("\n[!] Da ghi log loi: %s" % ERR_LOG)

    by_type, by_method = {}, {}
    for r in ent_rows:
        by_type[r["entity_type"]] = by_type.get(r["entity_type"], 0) + 1
        by_method[r["method"]] = by_method.get(r["method"], 0) + 1

    n_lv = sum(1 for r in enr_rows if is_unclear(r.get("linh_vuc")) and r.get("linh_vuc_enriched"))
    n_nk = sum(1 for r in enr_rows if is_unclear(r.get("nguoi_ky")) and r.get("nguoi_ky_enriched"))
    n_cq = sum(1 for r in enr_rows if is_unclear(r.get("co_quan_ban_hanh")) and r.get("co_quan_enriched"))
    n_dta = sum(1 for r in enr_rows if r.get("doi_tuong_ap_dung"))
    n_flag = sum(1 for r in enr_rows if r.get("enrichment_notes", "").strip())

    print("\n" + "=" * 66)
    print("KET QUA BUOC 3 (GEMINI THAT)")
    print("=" * 66)
    if models_used:
        print("[Model da su dung]")
        for m, c in models_used.items():
            print("  %-30s %d document" % (m, c))
        print()
    print("Document goi Gemini thanh cong : %d/%d" % (n_ok, len(docs)))
    print("Document loi (khong dung batch) : %d/%d" % (n_fail, len(docs)))
    print("Entity bi loai do evidence khong khop van ban: %d" % n_filtered)
    print("\n[Entity theo loai]")
    for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
        print("  %-16s %d" % (k, v))
    print("\n[Entity theo method]")
    for k, v in sorted(by_method.items(), key=lambda x: -x[1]):
        print("  %-18s %d" % (k, v))
    print("\n[Metadata duoc bo sung]")
    print("  linh_vuc  : %d" % n_lv)
    print("  co_quan   : %d" % n_cq)
    print("  nguoi_ky  : %d" % n_nk)
    print("  doi_tuong_ap_dung co du lieu: %d/%d" % (n_dta, len(enr_rows)))
    print("  document CAN XEM LAI: %d" % n_flag)

    print("\n[5 vi du metadata goc vs lam giau]")
    for r in enr_rows[:5]:
        print("\n  id=%s  so_ky_hieu=%s" % (r.get("id"), r.get("so_ky_hieu")))
        print("    linh_vuc goc='%s' -> enriched='%s'" % (r.get("linh_vuc"), r.get("linh_vuc_enriched")))
        print("    nguoi_ky goc='%s' -> enriched='%s'" % (r.get("nguoi_ky"), r.get("nguoi_ky_enriched")))
        d = r.get("doi_tuong_ap_dung") or "(khong co)"
        print("    doi_tuong_ap_dung: %s" % d[:160])
        if r.get("enrichment_notes", "").strip():
            print("    *** %s" % r["enrichment_notes"])

    if errors:
        print("\n[Danh sach loi] (%d)" % len(errors))
        for did, sky, et, msg in errors[:10]:
            print("  id=%s  %s  %s: %s" % (did, sky, et, msg[:120]))

    print("\nPASS/FAIL:")
    print("  [%s] Goi Gemini thanh cong it nhat 1 document" % ("PASS" if n_ok else "FAIL"))
    print("  [%s] Khong phai toan bo batch loi" % ("PASS" if n_fail < len(docs) else "FAIL"))
    print("  [PASS] Khong ghi de metadata.csv / content.csv / cleaned_documents.csv")
    print("\n[Output] %s" % OUT_ENT)
    print("[Output] %s" % OUT_ENR)


if __name__ == "__main__":
    main()
