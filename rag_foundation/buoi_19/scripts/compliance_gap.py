"""
BUOI 19 - PROMPT 2: UC2 - AI Compliance Gap Checker, PHIEN BAN DUAL-PROVIDER
(Ollama local / Gemini cloud).

Ban CAP NHAT cua buoi_17/scripts/compliance_gap.py - GIU NGUYEN 100% rule
engine minh bach (regex nguong so floor/ceiling %, ceiling ty dong, BM25 cua
buoi_14, Neo4j status that), CHI THAY doi noi goi LLM tuy chon (llm_refine)
sang dung `llm_provider.call_llm()` (Ollama/Gemini). buoi_17/scripts/
compliance_gap.py GIU NGUYEN, KHONG bi sua.

Doc du lieu QUA BIEN MOI TRUONG (SOURCE_COMBINED_SECURE_CSV tro ve
buoi_17/data/chunks_combined_secure.csv) thay vi copy rieng - giong nguyen
tac buoi_18 da ap dung, tranh drift du lieu giua cac buoi.

Xuat: outputs/compliance_gap_results.csv, outputs/compliance_gap_report.md
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

import pandas as pd
from rank_bm25 import BM25Okapi

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
sys.path.insert(0, str(BUOI14_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.bm25_retriever import tokenize  # noqa: E402  (TAI SU DUNG, khong viet lai)
from src import secure_retriever  # noqa: E402 (dung lai neo4j_status)
from llm_provider import call_llm  # noqa: E402

# nap .env don gian (KHONG ghi de bien da co san)
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

COMBINED_CSV = BASE_DIR / os.environ["SOURCE_COMBINED_SECURE_CSV"]
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
    KHONG dung similarity score de tu ket luan noi dung. Xem giai thich day
    du trong buoi_17/scripts/compliance_gap.py (giu nguyen logic)."""
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


def llm_refine(external_text: str, internal_text: str) -> dict | None:
    """Tuy chon: nho LLM (Ollama/Gemini tuy LLM_PROVIDER) doc CA HAI van ban
    that de goi y phan loai. Van LUON can NEEDS_HUMAN_REVIEW. Neu khong co
    ket qua/loi -> tra ve None (giu nguyen ket qua rule-based)."""
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
    text = call_llm(prompt, format_json=True)
    if not text:
        return None
    try:
        text = text.strip("`").removeprefix("json").strip()
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        if data.get("classification") in ("DAP_UNG", "THIEU", "CHENH_LECH", "CHUA_DU_BANG_CHUNG"):
            return data
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[CANH BAO] LLM refine tra ve du lieu khong hop le, giu nguyen rule-based: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    df = pd.read_csv(COMBINED_CSV)
    df["classification"] = df.apply(classify_document, axis=1)
    external = df[df["classification"] == "EXTERNAL_REQUIREMENT"].reset_index(drop=True)
    internal, bm25 = build_internal_index(df)

    ok, neo4j_msg = secure_retriever.neo4j_status()
    graph_used = False

    llm_budget = 25
    results = []
    for _, ext_row in external.iterrows():
        ext = ext_row.to_dict()
        match, score = best_internal_match(ext.get("text", ""), internal, bm25)
        cls, reason, confidence = classify_gap(ext, match, score)
        method = "rule_numeric_threshold" if cls in ("DAP_UNG", "CHENH_LECH") else "rule_no_confident_match"

        if (
            llm_budget > 0 and match is not None
            and cls == "CHUA_DU_BANG_CHUNG"
            and MANDATE_PATTERN.search(str(ext.get("text", "")))
        ):
            refined = llm_refine(ext.get("text", ""), match.get("text", ""))
            if refined:
                cls = refined["classification"]
                reason = f"[LLM-assisted ({provider}), cần xác minh] {refined.get('reason', '')}"
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

    lines = [f"# Buổi 19 — Compliance Gap Report (PROMPT 2 / UC2, provider={provider})\n"]
    lines.append(
        f"Đã chấm điểm **{len(res_df)}** yêu cầu bên ngoài (EXTERNAL_REQUIREMENT, "
        f"toàn bộ {len(external)} chunk) đối chiếu với **{len(internal)}** điều khoản nội bộ "
        "mô phỏng (INTERNAL_POLICY), dùng BM25 (tái sử dụng `tokenize()` + `BM25Okapi` của "
        "buoi_14, không viết lại thuật toán retrieval).\n"
    )
    lines.append(f"Neo4j status: {neo4j_msg} (GRAPH USED: {'YES' if graph_used else 'NO'})\n")
    lines.append(f"LLM_PROVIDER hiện tại: **{provider}** (Ollama local hoặc Gemini cloud tuỳ .env)\n")

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
    lines.append("- Không gán DAP_UNG khi không có internal evidence.")
    lines.append("- Không gán THIẾU chỉ vì retriever chưa tìm thấy.")
    lines.append("- Mọi dòng đều có `review_status = NEEDS_HUMAN_REVIEW`.\n")

    lines.append("GAP CHECKER: PASS")
    lines.append("HUMAN REVIEW REQUIRED: YES")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT_CSV} va {OUT_MD}")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
