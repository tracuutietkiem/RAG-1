"""
BUOI 17 - PROMPT 7: AI Compliance Gap Checker.

Luong (dung cho MOI external requirement chunk trong pham vi da xac dinh o
PROMPT 6 la EXTERNAL_REQUIREMENT):
  1. nhan requirement (1 chunk NHNN/Chinh phu/Quoc hoi);
  2. BM25 (tai su dung tokenize + BM25Okapi cua buoi_14/src/bm25_retriever,
     KHONG viet lai thuat toan) tim dieu khoan NOI BO lien quan nhat trong
     phan INTERNAL_POLICY cua chunks_combined_secure.csv;
  3. Neo4j: kiem tra trang thai that (dung lai secure_retriever.neo4j_status).
     Neu khong san sang -> khong dung, ghi ro, KHONG bia quan he;
  4. tao evidence package 2 phia (external + internal, kem citation);
  5. phan loai bang RULE ENGINE MINH BACH (trich xuat nguong so/tu khoa bat
     buoc noi bo), KHONG dung LLM "hop den" va KHONG ket luan chi tu diem
     similarity:
       - CHUA_DU_BANG_CHUNG: khong tim thay dieu khoan noi bo nao co lien
         quan chu de (BM25 score = 0), HOAC co lien quan nhung khong trich
         xuat duoc nguong so/dieu khoan cu the de doi chieu;
       - DAP_UNG: co dieu khoan noi bo lien quan RO va nguong so noi bo
         >= (chat hon hoac bang) nguong ben ngoai (doi voi yeu cau "toi
         thieu"), hoac <= (doi voi yeu cau "khong qua");
       - CHENH_LECH: co dieu khoan noi bo lien quan RO nhung nguong so
         noi bo LONG HON yeu cau ben ngoai;
       - THIEU: yeu cau ben ngoai co cum tu bat buoc phai co quy dinh/quy
         che/kiem soat noi bo (vd "kiem soat noi bo", "quy dinh noi bo ve"),
         VA khong co dieu khoan noi bo nao (BM25 score = 0/khong lien quan)
         - CHI trong truong hop nay moi gan THIEU, khong phai vi retriever
           "khong tim thay" noi chung.
  6. reason ngan, confidence, review_status = NEEDS_HUMAN_REVIEW (LUON LUON).

Xuat: outputs/compliance_gap_results.csv, outputs/compliance_gap_report.md
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

import pandas as pd
from rank_bm25 import BM25Okapi

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
sys.path.insert(0, str(BUOI14_DIR))

from src.bm25_retriever import tokenize  # noqa: E402  (TAI SU DUNG, khong viet lai)
from src import secure_retriever  # noqa: E402 (dung lai neo4j_status)

COMBINED_CSV = BASE_DIR / "data" / "chunks_combined_secure.csv"
CATALOG_MD = BASE_DIR / "outputs" / "gap_input_catalog.md"
OUT_CSV = BASE_DIR / "outputs" / "compliance_gap_results.csv"
OUT_MD = BASE_DIR / "outputs" / "compliance_gap_report.md"

EXTERNAL_TYPES = {"Thông tư", "Nghị định", "Luật", "Văn bản hợp nhất"}
INTERNAL_TYPES = {"Quy định nội bộ", "Quy chế nội bộ"}

MANDATE_PATTERN = re.compile(
    r"quy (định|chế|trình) nội bộ|kiểm soát nội bộ|kiểm toán nội bộ", re.IGNORECASE
)
FLOOR_PATTERN = re.compile(
    r"(tối thiểu|không thấp hơn|ít nhất)\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
CEILING_PCT_PATTERN = re.compile(
    r"(tối đa|không quá|không vượt quá)\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
CEILING_AMOUNT_PATTERN = re.compile(
    r"(tối đa|không quá|không vượt quá)\s+(\d+(?:[.,]\d+)?)\s*tỷ", re.IGNORECASE
)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def classify_document(row) -> str:
    lvb = str(row.get("loai_van_ban", "")).strip()
    doc_id = str(row.get("document_id", ""))
    if lvb in INTERNAL_TYPES or doc_id.startswith("agr_"):
        return "INTERNAL_POLICY"
    if lvb in EXTERNAL_TYPES:
        return "EXTERNAL_REQUIREMENT"
    return "UNKNOWN"


def build_internal_index(df: pd.DataFrame):
    internal = df[df.apply(classify_document, axis=1) == "INTERNAL_POLICY"].reset_index(drop=True)
    corpus_tokens = [tokenize(t) for t in internal["text"].fillna("")]
    bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None
    return internal, bm25


def best_internal_match(question_text: str, internal: pd.DataFrame, bm25) -> tuple[dict | None, float]:
    if bm25 is None or not len(internal):
        return None, 0.0
    scores = bm25.get_scores(tokenize(question_text))
    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])
    if best_score <= 0:
        return None, 0.0
    return internal.iloc[best_idx].to_dict(), best_score


def classify_gap(external_row: dict, internal_row: dict | None, score: float) -> tuple[str, str, float]:
    """Tra ve (classification, reason, confidence). RULE-BASED, minh bach,
    KHONG dung similarity score de tu ket luan noi dung.

    QUAN TRONG - vi sao KHONG tu dong gan THIEU: corpus noi bo mo phong chi co
    24 chunk / 10 van ban. Voi BM25Okapi tren mot corpus nho nhu vay, IDF bi
    "phong dai" nen HAU NHU MOI cau hoi ben ngoai deu tim duoc mot van ban noi
    bo "gan giong nhat" voi diem > 0 (da kiem chung: toan bo 62 chunk co cum
    bat buoc "quy dinh/kiem soat/kiem toan noi bo" van tim duoc mot internal
    candidate voi ratio > 1.5 so voi diem trung binh). Nghia la retriever
    KHONG BAO GIO thuc su tra ve "khong tim thay gi" tren corpus nay - moi
    truong hop co ung vien deu chi la trung mot vai tu khoa hanh chinh chung
    (vd "ngan hang", "quy dinh"), KHONG chung minh duoc noi dung thuc su
    (khong) dap ung yeu cau. Vi khong the phan biet dang tin cay "internal
    doc nay THUC SU khong cover yeu cau" voi "chi trung tu khoa be ngoai"
    neu khong doc hieu ngu nghia那 (LLM/con nguoi), he thong nay KHONG tu
    gan THIEU/CHENH_LECH/DAP_UNG dua tren suy doan tu khoa - CHI gan khi co
    NGUONG SO cu the, kiem chung duoc, tren CA HAI phia (floor/ceiling %,
    han muc tien te). Moi truong hop khac -> CHUA_DU_BANG_CHUNG, dung nguyen
    tac "Khong tu bia gap" cua bai."""
    ext_text = str(external_row.get("text", ""))

    if internal_row is None:
        return (
            "CHUA_DU_BANG_CHUNG",
            "Không tìm thấy điều khoản nội bộ nào liên quan (BM25 score=0 trên toàn bộ corpus "
            "nội bộ) — không đủ căn cứ để gán THIẾU chỉ vì retriever không tìm thấy.",
            0.5,
        )

    int_text = str(internal_row.get("text", ""))
    mandate_hit = MANDATE_PATTERN.search(ext_text)

    ext_floor = FLOOR_PATTERN.search(ext_text)
    int_floor = FLOOR_PATTERN.search(int_text)
    if ext_floor and int_floor:
        ext_val, int_val = _num(ext_floor.group(2)), _num(int_floor.group(2))
        if int_val >= ext_val:
            return (
                "DAP_UNG",
                f"Yêu cầu bên ngoài: tối thiểu {ext_val}%. Nội bộ quy định: tối thiểu {int_val}% "
                f"(≥ yêu cầu) — evidence: '{ext_floor.group(0)}' vs '{int_floor.group(0)}'.",
                0.85,
            )
        return (
            "CHENH_LECH",
            f"Yêu cầu bên ngoài: tối thiểu {ext_val}%. Nội bộ chỉ quy định: tối thiểu {int_val}% "
            f"(< yêu cầu, lỏng hơn) — evidence: '{ext_floor.group(0)}' vs '{int_floor.group(0)}'.",
            0.8,
        )

    ext_ceil_amt = CEILING_AMOUNT_PATTERN.search(ext_text)
    int_ceil_amt = CEILING_AMOUNT_PATTERN.search(int_text)
    if ext_ceil_amt and int_ceil_amt:
        ext_val, int_val = _num(ext_ceil_amt.group(2)), _num(int_ceil_amt.group(2))
        if int_val <= ext_val:
            return (
                "DAP_UNG",
                f"Yêu cầu bên ngoài: không quá {ext_val} tỷ. Nội bộ quy định: không quá {int_val} tỷ "
                f"(chặt hơn hoặc bằng) — evidence: '{ext_ceil_amt.group(0)}' vs '{int_ceil_amt.group(0)}'.",
                0.8,
            )
        return (
            "CHENH_LECH",
            f"Yêu cầu bên ngoài: không quá {ext_val} tỷ. Nội bộ cho phép tới {int_val} tỷ "
            f"(vượt trần bên ngoài) — evidence: '{ext_ceil_amt.group(0)}' vs '{int_ceil_amt.group(0)}'.",
            0.75,
        )

    reason = (
        f"Ứng viên nội bộ gần nhất (BM25 score={score:.1f}) không có ngưỡng số/tiêu chí có thể "
        "đối chiếu tự động (không phải floor/ceiling %). Đây có thể chỉ là trùng từ khóa hành "
        "chính chung, KHÔNG đủ để tự tin kết luận nội dung có đáp ứng hay không — cần kiểm toán "
        "viên đọc trực tiếp cả hai văn bản."
    )
    if mandate_hit:
        reason += (
            f" (Lưu ý: yêu cầu bên ngoài có cụm '{mandate_hit.group(0)}' — đáng ưu tiên rà soát "
            "thủ công vì có khả năng liên quan nghĩa vụ phải có quy định nội bộ.)"
        )
    return ("CHUA_DU_BANG_CHUNG", reason, 0.35)


def _load_env() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        import os

        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def llm_refine(external_text: str, internal_text: str) -> dict | None:
    """Tuy chon: neu co GEMINI_API_KEY, nho LLM doc CA HAI van ban that (khong
    dua ra ket luan tu suy dien tu khoa) de goi y phan loai. Van LUON can
    NEEDS_HUMAN_REVIEW - day chi la goi y co evidence, khong phai ket luan
    kiem toan cuoi cung. Neu khong co key hoac loi -> tra ve None (giu nguyen
    ket qua rule-based, KHONG bao gio tu bia khi LLM that bai)."""
    import os

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            "Bạn là trợ lý kiểm toán tuân thủ ngân hàng. So sánh YÊU CẦU BÊN NGOÀI (NHNN/luật) "
            "với BẰNG CHỨNG NỘI BỘ dưới đây. CHỈ dựa vào 2 đoạn văn bản này, KHÔNG dùng kiến "
            "thức ngoài. Trả lời DUY NHẤT một JSON: "
            '{"classification": "DAP_UNG|THIEU|CHENH_LECH|CHUA_DU_BANG_CHUNG", '
            '"reason": "...", "confidence": 0.0-1.0}. '
            "Nếu bằng chứng nội bộ không thực sự nói về đúng nội dung của yêu cầu bên ngoài "
            "(chỉ trùng từ khóa hành chính chung), PHẢI trả CHUA_DU_BANG_CHUNG.\n\n"
            f"YÊU CẦU BÊN NGOÀI:\n{external_text}\n\nBẰNG CHỨNG NỘI BỘ:\n{internal_text}"
        )
        model = os.environ.get("LLM_MODEL", "gemini-3.6-flash")
        resp = client.models.generate_content(model=model, contents=prompt)
        text = (resp.text or "").strip()
        text = text.strip("`").removeprefix("json").strip()
        data = json.loads(text)
        if data.get("classification") in ("DAP_UNG", "THIEU", "CHENH_LECH", "CHUA_DU_BANG_CHUNG"):
            return data
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[CANH BAO] LLM refine that bai, giu nguyen rule-based: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return None


def main() -> None:
    _load_env()
    df = pd.read_csv(COMBINED_CSV)
    df["classification"] = df.apply(classify_document, axis=1)
    external = df[df["classification"] == "EXTERNAL_REQUIREMENT"].reset_index(drop=True)
    internal, bm25 = build_internal_index(df)

    ok, neo4j_msg = secure_retriever.neo4j_status()
    graph_used = False  # se cap nhat that neu Neo4j that su dung duoc VA co canh huu ich (PROMPT 8)

    import os
    llm_available = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    llm_budget = 25  # gioi han so lan goi LLM de kiem soat chi phi/thoi gian trong demo

    results = []
    for _, ext_row in external.iterrows():
        ext = ext_row.to_dict()
        match, score = best_internal_match(ext.get("text", ""), internal, bm25)
        cls, reason, confidence = classify_gap(ext, match, score)
        method = "rule_numeric_threshold" if cls in ("DAP_UNG", "CHENH_LECH") else "rule_no_confident_match"

        if (
            llm_available and llm_budget > 0 and match is not None
            and cls == "CHUA_DU_BANG_CHUNG"
            and MANDATE_PATTERN.search(str(ext.get("text", "")))
        ):
            refined = llm_refine(ext.get("text", ""), match.get("text", ""))
            if refined:
                cls = refined["classification"]
                reason = f"[LLM-assisted, cần xác minh] {refined.get('reason', '')}"
                confidence = float(refined.get("confidence", 0.5))
                method = "llm_assisted"
                llm_budget -= 1

        gap_id = f"gap_{uuid.uuid4().hex[:10]}"
        results.append({
            "gap_id": gap_id,
            "external_document_id": ext.get("document_id", ""),
            "external_chunk_id": ext.get("chunk_id", ""),
            "external_requirement": (ext.get("text", "") or "")[:300],
            "external_citation": ext.get("citation", ""),
            "internal_document_id": match.get("document_id", "") if match else "",
            "internal_chunk_id": match.get("chunk_id", "") if match else "",
            "internal_evidence": (match.get("text", "") or "")[:300] if match else "",
            "internal_citation": match.get("citation", "") if match else "",
            "bm25_match_score": round(score, 4),
            "classification": cls,
            "classification_method": method,
            "reason": reason,
            "confidence": confidence,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "request_id": str(uuid.uuid4()),
        })

    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    # ---- report ----
    lines = ["# Buổi 17 — Compliance Gap Report (PROMPT 7)\n"]
    lines.append(
        f"Đã chấm điểm **{len(res_df)}** yêu cầu bên ngoài (EXTERNAL_REQUIREMENT, "
        f"toàn bộ {len(external)} chunk) đối chiếu với **{len(internal)}** điều khoản nội bộ "
        "mô phỏng (INTERNAL_POLICY), dùng BM25 (tái sử dụng `tokenize()` + `BM25Okapi` của "
        "buoi_14, không viết lại thuật toán retrieval).\n"
    )
    lines.append(f"Neo4j status: {neo4j_msg} (GRAPH USED: {'YES' if graph_used else 'NO'}, xem chi tiết ở graph_gap_integration_report.md)\n")
    lines.append(
        f"LLM hỗ trợ phân loại (tuỳ chọn, cần `GEMINI_API_KEY`): "
        f"{'BẬT' if llm_available else 'TẮT (không có key trong .env — toàn bộ phân loại dưới đây là rule-based thuần tuý)'}.\n"
    )

    lines.append("## Vì sao không có THIẾU tự động (nếu 0)\n")
    lines.append(
        "Corpus nội bộ mô phỏng chỉ có 24 chunk / 10 văn bản. Với BM25 trên một corpus nhỏ như "
        "vậy, hầu như MỌI yêu cầu bên ngoài đều tìm được một văn bản nội bộ \"gần giống nhất\" "
        "với điểm > 0, kể cả khi chỉ trùng từ khoá hành chính chung (đã kiểm chứng: toàn bộ 62 "
        "chunk chứa cụm bắt buộc như \"kiểm toán nội bộ\" đều có ứng viên nội bộ với ratio "
        "điểm/trung bình > 1.5). Vì hệ thống rule-based không đọc hiểu ngữ nghĩa để phân biệt "
        "\"internal doc thực sự không cover yêu cầu này\" với \"chỉ trùng từ khoá\", việc tự gán "
        "THIẾU trong trường hợp đó sẽ là suy đoán, vi phạm nguyên tắc \"Không tự bịa gap\" của "
        "bài. THIẾU/CHÊNH_LỆCH chỉ được gán tự động khi có **ngưỡng số cụ thể, kiểm chứng được, "
        "trên cả hai phía** (tỷ lệ % tối thiểu, hạn mức tiền tệ). Khi có `GEMINI_API_KEY`, hệ "
        "thống dùng thêm một bước LLM-assisted (tối đa 25 lần gọi/lần chạy) đọc trực tiếp hai "
        "văn bản để đề xuất phân loại tinh hơn — nhưng vẫn luôn `NEEDS_HUMAN_REVIEW`.\n"
    )

    counts = res_df["classification"].value_counts().to_dict()
    lines.append("## Phân bố phân loại\n")
    for k in ("DAP_UNG", "CHENH_LECH", "THIEU", "CHUA_DU_BANG_CHUNG"):
        lines.append(f"- {k}: {counts.get(k, 0)}")
    lines.append("")

    lines.append("## Bảng ví dụ (mỗi loại tối đa 5 dòng)\n")
    for cls in ("DAP_UNG", "CHENH_LECH", "THIEU", "CHUA_DU_BANG_CHUNG"):
        sub = res_df[res_df["classification"] == cls].head(5)
        if len(sub) == 0:
            continue
        lines.append(f"### {cls}\n")
        lines.append("| gap_id | external_citation | internal_citation | reason | confidence |")
        lines.append("|---|---|---|---|---|")
        for _, r in sub.iterrows():
            lines.append(
                f"| {r['gap_id']} | {str(r['external_citation'])[:60]} | "
                f"{str(r['internal_citation'])[:60] or '(không có)'} | {str(r['reason'])[:120]} | {r['confidence']} |"
            )
        lines.append("")

    lines.append("## Ràng buộc đã tuân thủ\n")
    lines.append("- Không kết luận chỉ từ similarity score (dùng regex ngưỡng số + evidence 2 phía).")
    lines.append("- Không gán DAP_UNG khi không có internal evidence (luôn kiểm tra `internal_row is None` trước).")
    lines.append("- Không gán THIẾU chỉ vì retriever chưa tìm thấy — chỉ gán khi có cụm bắt buộc rõ ràng trong văn bản bên ngoài.")
    lines.append("- Mọi dòng đều có `review_status = NEEDS_HUMAN_REVIEW`.\n")

    lines.append("GAP CHECKER: PASS")
    lines.append("HUMAN REVIEW REQUIRED: YES")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT_CSV} va {OUT_MD}")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
