"""
BƯỚC 3 — Entity Extraction và Metadata Enrichment bằng Gemini

Input:
  ner_kb/cleaned_documents.csv

Output:
  ner_kb/extracted_entities_raw.csv
  ner_kb/enriched_metadata.csv

Nguyên tắc:
  - Ưu tiên metadata gốc khi giá trị đã rõ (không để Gemini ghi đè).
  - Gemini dùng để: bổ sung missing, phân loại "Chưa phân loại",
    trích xuất DoiTuongApDung, làm giàu LinhVuc, gắn cờ metadata cần xem lại.
  - Không có evidence -> không tạo entity.
  - Lỗi API / response rỗng / JSON hỏng -> ghi nhận lỗi, KHÔNG dừng batch.
  - Không tự đặt confidence = 1 cho entity do Gemini suy luận.
  - Không log GEMINI_API_KEY.
  - Không sửa metadata.csv / content.csv / cleaned_documents.csv.
"""
import os
import re
import sys
import json
import time
import traceback

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE = os.path.dirname(os.path.abspath(__file__))
IN_PATH = os.path.join(BASE, "ner_kb", "cleaned_documents.csv")
OUT_ENTITIES = os.path.join(BASE, "ner_kb", "extracted_entities_raw.csv")
OUT_ENRICHED = os.path.join(BASE, "ner_kb", "enriched_metadata.csv")
ERROR_LOG = os.path.join(BASE, "loi_buoc3_gemini.txt")

load_dotenv(os.path.join(BASE, ".env"))
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

HEAD_CHARS = 9000
TAIL_CHARS = 4000

UNCLEAR_VALUES = {"", "nan", "none", "chưa phân loại", "null"}


def is_unclear(v) -> bool:
    if v is None:
        return True
    s = str(v).strip().lower()
    return s in UNCLEAR_VALUES


def make_excerpt(text: str) -> str:
    if not isinstance(text, str):
        return ""
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text
    return (
        text[:HEAD_CHARS]
        + "\n\n[... đã lược bớt phần giữa văn bản ...]\n\n"
        + text[-TAIL_CHARS:]
    )


PROMPT_TEMPLATE = """Bạn là chuyên gia phân tích văn bản pháp luật ngân hàng Việt Nam.
Đọc đoạn trích văn bản dưới đây và trích xuất CHÍNH XÁC các thông tin sau, CHỈ dựa trên
nội dung có trong đoạn trích. TUYỆT ĐỐI KHÔNG suy diễn hay bịa thông tin không có evidence.

Metadata gốc đã có (tham khảo để đối chiếu, KHÔNG ghi đè nếu đã rõ ràng):
- co_quan_ban_hanh (metadata gốc): {meta_co_quan}
- nguoi_ky (metadata gốc): {meta_nguoi_ky}
- linh_vuc (metadata gốc): {meta_linh_vuc}

Nhiệm vụ:
1. co_quan: Cơ quan ban hành văn bản. Nếu đoạn trích xác nhận đúng giá trị metadata gốc,
   vẫn trả về entity đó kèm evidence trích trực tiếp từ đoạn trích, matches_metadata=true.
   Nếu phát hiện KHÁC với metadata gốc, trả về giá trị đúng theo văn bản, matches_metadata=false.
2. nguoi_ky: Người ký / người có thẩm quyền ban hành (thường ở cuối văn bản, dưới chức danh
   như "TL. THỐNG ĐỐC", "KT. BỘ TRƯỞNG", "CHỦ TỊCH QUỐC HỘI"...). Xử lý tương tự co_quan.
3. doi_tuong_ap_dung: Liệt kê TỪNG đối tượng chịu sự điều chỉnh RIÊNG BIỆT (mỗi đối tượng
   một entity, không gộp chung thành một câu dài), thường ở phần "Đối tượng áp dụng".
   Nếu văn bản không có mục này rõ ràng, trả về mảng rỗng.
4. linh_vuc: CHỈ đề xuất nếu metadata gốc đang thiếu/rỗng/"Chưa phân loại" (xem giá trị
   metadata gốc ở trên). Nếu metadata gốc đã có giá trị rõ ràng, trả về mảng rỗng cho mục này.
   Lĩnh vực nghiệp vụ ngân hàng/tài chính, ví dụ: Tín dụng, Kiểm toán, Bảo hiểm, Chứng khoán,
   Quản lý ngoại hối, Phát hành và kho quỹ, Thanh tra giám sát ngân hàng...

Với MỖI entity, bắt buộc có:
- entity: tên thực thể (ngắn gọn, chuẩn)
- evidence: đoạn text trích DẪN NGUYÊN VĂN từ đoạn trích chứng minh (không tự viết lại)
- confidence: số 0.0-1.0, phản ánh trung thực mức chắc chắn (không phải lúc nào cũng 1.0;
  giá trị nêu tường minh, trực tiếp trong văn bản mới cho >=0.85; giá trị suy luận gián tiếp
  cho thấp hơn)

Nếu KHÔNG có bằng chứng cho một mục nào đó, trả về mảng rỗng [] cho mục đó, TUYỆT ĐỐI
không bịa entity.

Chỉ trả về JSON đúng theo schema, không thêm giải thích, không markdown code fence:
{{
  "co_quan": [{{"entity": "...", "evidence": "...", "confidence": 0.0, "matches_metadata": true}}],
  "nguoi_ky": [{{"entity": "...", "evidence": "...", "confidence": 0.0, "matches_metadata": true}}],
  "doi_tuong_ap_dung": [{{"entity": "...", "evidence": "...", "confidence": 0.0}}],
  "linh_vuc": [{{"entity": "...", "evidence": "...", "confidence": 0.0}}]
}}

--- ĐOẠN TRÍCH VĂN BẢN (id={doc_id}, số hiệu={so_ky_hieu}) ---
{excerpt}
--- HẾT ĐOẠN TRÍCH ---
"""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "co_quan": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity": {"type": "STRING"},
                    "evidence": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "matches_metadata": {"type": "BOOLEAN"},
                },
                "required": ["entity", "evidence", "confidence"],
            },
        },
        "nguoi_ky": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity": {"type": "STRING"},
                    "evidence": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "matches_metadata": {"type": "BOOLEAN"},
                },
                "required": ["entity", "evidence", "confidence"],
            },
        },
        "doi_tuong_ap_dung": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity": {"type": "STRING"},
                    "evidence": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["entity", "evidence", "confidence"],
            },
        },
        "linh_vuc": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity": {"type": "STRING"},
                    "evidence": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["entity", "evidence", "confidence"],
            },
        },
    },
    "required": ["co_quan", "nguoi_ky", "doi_tuong_ap_dung", "linh_vuc"],
}


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def evidence_grounded(evidence: str, full_text: str) -> bool:
    """Kiểm tra evidence có thực sự xuất hiện (gần đúng) trong văn bản gốc không."""
    if not evidence or not isinstance(evidence, str):
        return False
    ev = normalize_ws(evidence)
    doc = normalize_ws(full_text)
    if not ev:
        return False
    if ev in doc:
        return True
    # khớp lỏng: >=80% độ dài cụm evidence xuất hiện liên tục trong doc
    if len(ev) > 20:
        chunk = ev[: max(20, int(len(ev) * 0.7))]
        if chunk in doc:
            return True
    return False


def call_gemini(client, doc_id, so_ky_hieu, excerpt, meta_co_quan, meta_nguoi_ky, meta_linh_vuc):
    prompt = PROMPT_TEMPLATE.format(
        doc_id=doc_id,
        so_ky_hieu=so_ky_hieu,
        excerpt=excerpt,
        meta_co_quan=meta_co_quan if not is_unclear(meta_co_quan) else "(thiếu/chưa rõ)",
        meta_nguoi_ky=meta_nguoi_ky if not is_unclear(meta_nguoi_ky) else "(thiếu/chưa rõ)",
        meta_linh_vuc=meta_linh_vuc if not is_unclear(meta_linh_vuc) else "(thiếu/chưa rõ - CẦN Gemini phân loại)",
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.1,
        ),
    )
    return response.text


def main():
    if not API_KEY:
        print("[FAIL] Không tìm thấy GEMINI_API_KEY trong .env. Dừng lại.")
        sys.exit(1)

    df = pd.read_csv(IN_PATH, dtype=str)
    print("=" * 70)
    print("BƯỚC 3 — GEMINI ENTITY EXTRACTION & METADATA ENRICHMENT")
    print("=" * 70)
    print(f"Input: {len(df)} document | model={MODEL}")

    client = genai.Client(api_key=API_KEY)

    entity_rows = []
    enriched_rows = []
    errors = []
    n_success = 0
    n_fail = 0
    n_entities_filtered_no_evidence = 0

    for i, row in df.iterrows():
        doc_id = row["id"]
        so_ky_hieu = row.get("so_ky_hieu", "")
        content_clean = row.get("content_clean", "") or ""
        meta_co_quan = row.get("co_quan_ban_hanh")
        meta_nguoi_ky = row.get("nguoi_ky")
        meta_linh_vuc = row.get("linh_vuc")

        enriched = row.to_dict()  # giữ nguyên toàn bộ metadata gốc + content_clean
        enriched["co_quan_enriched"] = meta_co_quan if not is_unclear(meta_co_quan) else None
        enriched["nguoi_ky_enriched"] = meta_nguoi_ky if not is_unclear(meta_nguoi_ky) else None
        enriched["linh_vuc_enriched"] = meta_linh_vuc if not is_unclear(meta_linh_vuc) else None
        enriched["doi_tuong_ap_dung"] = None
        enriched["enrichment_notes"] = ""

        # 1. Entity lấy trực tiếp từ metadata gốc khi đã rõ (ƯU TIÊN, không chờ Gemini)
        if not is_unclear(meta_co_quan):
            entity_rows.append({
                "entity": str(meta_co_quan).strip(), "entity_type": "CoQuan",
                "source": "metadata", "method": "metadata_original",
                "confidence": 1.0, "evidence": f"metadata.csv: co_quan_ban_hanh = '{meta_co_quan}'",
            })
        if not is_unclear(meta_nguoi_ky):
            entity_rows.append({
                "entity": str(meta_nguoi_ky).strip(), "entity_type": "NguoiKy",
                "source": "metadata", "method": "metadata_original",
                "confidence": 1.0, "evidence": f"metadata.csv: nguoi_ky = '{meta_nguoi_ky}'",
            })
        if not is_unclear(meta_linh_vuc):
            entity_rows.append({
                "entity": str(meta_linh_vuc).strip(), "entity_type": "LinhVuc",
                "source": "metadata", "method": "metadata_original",
                "confidence": 1.0, "evidence": f"metadata.csv: linh_vuc = '{meta_linh_vuc}'",
            })

        # 2. Gọi Gemini (luôn gọi để: validate CoQuan/NguoiKy, trích DoiTuongApDung,
        #    và làm giàu LinhVuc nếu đang thiếu)
        excerpt = make_excerpt(content_clean)
        parsed = None
        try:
            raw_text = call_gemini(
                client, doc_id, so_ky_hieu, excerpt, meta_co_quan, meta_nguoi_ky, meta_linh_vuc
            )
            if not raw_text or not raw_text.strip():
                raise ValueError("Gemini trả về response rỗng")
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            n_fail += 1
            errors.append({"id": doc_id, "so_ky_hieu": so_ky_hieu,
                            "error_type": "invalid_json", "message": str(e)})
        except Exception as e:
            n_fail += 1
            errors.append({"id": doc_id, "so_ky_hieu": so_ky_hieu,
                            "error_type": type(e).__name__, "message": str(e)})

        if parsed is not None:
            n_success += 1
            full_text_for_grounding = content_clean  # kiểm evidence trên toàn văn, không chỉ excerpt

            # --- co_quan (Gemini) ---
            for ent in parsed.get("co_quan", []) or []:
                if not evidence_grounded(ent.get("evidence", ""), full_text_for_grounding):
                    n_entities_filtered_no_evidence += 1
                    continue
                matches = ent.get("matches_metadata", True)
                if is_unclear(meta_co_quan) or not matches:
                    entity_rows.append({
                        "entity": str(ent.get("entity", "")).strip(), "entity_type": "CoQuan",
                        "source": "content_clean", "method": "gemini",
                        "confidence": float(ent.get("confidence", 0.5)),
                        "evidence": ent.get("evidence", "")[:400],
                    })
                    if not matches and not is_unclear(meta_co_quan):
                        enriched["enrichment_notes"] += (
                            f"[CoQuan] metadata='{meta_co_quan}' vs Gemini='{ent.get('entity')}' - CẦN XEM LẠI. "
                        )
                    if is_unclear(meta_co_quan):
                        enriched["co_quan_enriched"] = str(ent.get("entity", "")).strip()

            # --- nguoi_ky (Gemini) ---
            for ent in parsed.get("nguoi_ky", []) or []:
                if not evidence_grounded(ent.get("evidence", ""), full_text_for_grounding):
                    n_entities_filtered_no_evidence += 1
                    continue
                matches = ent.get("matches_metadata", True)
                if is_unclear(meta_nguoi_ky) or not matches:
                    entity_rows.append({
                        "entity": str(ent.get("entity", "")).strip(), "entity_type": "NguoiKy",
                        "source": "content_clean", "method": "gemini",
                        "confidence": float(ent.get("confidence", 0.5)),
                        "evidence": ent.get("evidence", "")[:400],
                    })
                    if not matches and not is_unclear(meta_nguoi_ky):
                        enriched["enrichment_notes"] += (
                            f"[NguoiKy] metadata='{meta_nguoi_ky}' vs Gemini='{ent.get('entity')}' - CẦN XEM LẠI. "
                        )
                    if is_unclear(meta_nguoi_ky):
                        enriched["nguoi_ky_enriched"] = str(ent.get("entity", "")).strip()

            # --- doi_tuong_ap_dung (luôn từ Gemini, metadata không có cột này) ---
            dta_list = []
            for ent in parsed.get("doi_tuong_ap_dung", []) or []:
                if not evidence_grounded(ent.get("evidence", ""), full_text_for_grounding):
                    n_entities_filtered_no_evidence += 1
                    continue
                entity_name = str(ent.get("entity", "")).strip()
                if not entity_name:
                    continue
                entity_rows.append({
                    "entity": entity_name, "entity_type": "DoiTuongApDung",
                    "source": "content_clean", "method": "gemini",
                    "confidence": float(ent.get("confidence", 0.5)),
                    "evidence": ent.get("evidence", "")[:400],
                })
                dta_list.append(entity_name)
            if dta_list:
                enriched["doi_tuong_ap_dung"] = "; ".join(dta_list)

            # --- linh_vuc (chỉ khi metadata thiếu) ---
            if is_unclear(meta_linh_vuc):
                for ent in parsed.get("linh_vuc", []) or []:
                    if not evidence_grounded(ent.get("evidence", ""), full_text_for_grounding):
                        n_entities_filtered_no_evidence += 1
                        continue
                    entity_rows.append({
                        "entity": str(ent.get("entity", "")).strip(), "entity_type": "LinhVuc",
                        "source": "content_clean", "method": "gemini",
                        "confidence": float(ent.get("confidence", 0.5)),
                        "evidence": ent.get("evidence", "")[:400],
                    })
                    if enriched["linh_vuc_enriched"] is None:
                        enriched["linh_vuc_enriched"] = str(ent.get("entity", "")).strip()

        enriched_rows.append(enriched)
        time.sleep(0.4)  # tránh rate limit

        if (i + 1) % 5 == 0 or (i + 1) == len(df):
            print(f"  ... đã xử lý {i + 1}/{len(df)} document")

    entities_df = pd.DataFrame(entity_rows, columns=[
        "entity", "entity_type", "source", "method", "confidence", "evidence"
    ])
    entities_df.to_csv(OUT_ENTITIES, index=False)

    enriched_df = pd.DataFrame(enriched_rows)
    enriched_df.to_csv(OUT_ENRICHED, index=False)

    # Ghi log lỗi (không chứa GEMINI_API_KEY)
    if errors:
        with open(ERROR_LOG, "w", encoding="utf-8") as f:
            f.write(f"BƯỚC 3 - Lỗi khi gọi Gemini ({len(errors)} document lỗi)\n")
            f.write("=" * 60 + "\n")
            for e in errors:
                f.write(f"id={e['id']}  so_ky_hieu={e['so_ky_hieu']}  "
                        f"loại_lỗi={e['error_type']}\n  message: {e['message']}\n\n")
        print(f"\n[!] Đã ghi log lỗi vào: {ERROR_LOG}")

    print("\n" + "=" * 70)
    print("KẾT QUẢ BƯỚC 3")
    print("=" * 70)
    print(f"Document gọi Gemini thành công : {n_success}/{len(df)}")
    print(f"Document lỗi (đã bỏ qua, không dừng batch): {n_fail}/{len(df)}")
    print(f"Entity bị loại do KHÔNG có evidence xác thực trong văn bản: {n_entities_filtered_no_evidence}")

    print("\n[Số entity theo loại]")
    print(entities_df["entity_type"].value_counts().to_string())

    print("\n[Số entity theo method]")
    print(entities_df["method"].value_counts().to_string())

    n_linh_vuc_filled = enriched_df.apply(
        lambda r: is_unclear(r.get("linh_vuc")) and not is_unclear(r.get("linh_vuc_enriched")), axis=1
    ).sum()
    n_co_quan_filled = enriched_df.apply(
        lambda r: is_unclear(r.get("co_quan_ban_hanh")) and not is_unclear(r.get("co_quan_enriched")), axis=1
    ).sum()
    n_nguoi_ky_filled = enriched_df.apply(
        lambda r: is_unclear(r.get("nguoi_ky")) and not is_unclear(r.get("nguoi_ky_enriched")), axis=1
    ).sum()
    n_dta_filled = enriched_df["doi_tuong_ap_dung"].notna().sum()
    n_review_flag = (enriched_df["enrichment_notes"].astype(str).str.strip() != "").sum()

    print(f"\n[Giá trị metadata được bổ sung]")
    print(f"  linh_vuc bổ sung   : {n_linh_vuc_filled}")
    print(f"  co_quan bổ sung    : {n_co_quan_filled}")
    print(f"  nguoi_ky bổ sung   : {n_nguoi_ky_filled}")
    print(f"  doi_tuong_ap_dung có dữ liệu: {n_dta_filled}/{len(enriched_df)}")
    print(f"  document được gắn cờ CẦN XEM LẠI: {n_review_flag}")

    print("\n[5 ví dụ metadata gốc so với metadata làm giàu]")
    sample = enriched_df.head(5)
    for _, r in sample.iterrows():
        print(f"\n  id={r['id']}  so_ky_hieu={r.get('so_ky_hieu')}")
        print(f"    linh_vuc gốc='{r.get('linh_vuc')}'  -> enriched='{r.get('linh_vuc_enriched')}'")
        print(f"    co_quan gốc='{r.get('co_quan_ban_hanh')}'  -> enriched='{r.get('co_quan_enriched')}'")
        print(f"    nguoi_ky gốc='{r.get('nguoi_ky')}'  -> enriched='{r.get('nguoi_ky_enriched')}'")
        dta = r.get("doi_tuong_ap_dung")
        print(f"    doi_tuong_ap_dung: {str(dta)[:200] if dta else '(không có)'}")
        if str(r.get("enrichment_notes", "")).strip():
            print(f"    *** CẦN XEM LẠI: {r['enrichment_notes']}")

    if errors:
        print(f"\n[Danh sách lỗi] ({len(errors)})")
        for e in errors:
            print(f"  id={e['id']}  so_ky_hieu={e['so_ky_hieu']}  {e['error_type']}: {e['message'][:150]}")

    print("\nPASS/FAIL:")
    print(f"[{'PASS' if os.path.exists(OUT_ENTITIES) else 'FAIL'}] extracted_entities_raw.csv được tạo")
    print(f"[{'PASS' if os.path.exists(OUT_ENRICHED) else 'FAIL'}] enriched_metadata.csv được tạo")
    print(f"[{'PASS' if n_success > 0 else 'FAIL'}] Ít nhất 1 document gọi Gemini thành công")
    print(f"[{'PASS' if n_fail < len(df) else 'FAIL'}] Không phải toàn bộ batch đều lỗi")
    print(f"[Output] {OUT_ENTITIES}")
    print(f"[Output] {OUT_ENRICHED}")


if __name__ == "__main__":
    main()
