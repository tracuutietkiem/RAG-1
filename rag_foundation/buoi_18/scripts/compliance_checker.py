"""
BUOI 18 - PROMPT 2: UC3 - AI Compliance Checker (so sanh cheo, phat hien
xung dot giua quy dinh noi bo Agribank va van ban phap luat / quy dinh noi
bo khac cung Domain).

Luong (cho MOI chunk noi bo trong pham vi da chon):
  1. Loc RBAC theo user_role (allowed_roles) TRUOC khi dua vao retrieval -
     giong nguyen tac cua buoi_14/buoi_17 (fail-closed).
  2. BM25 (tai su dung tokenize + BM25Okapi cua buoi_14/src/bm25_retriever,
     KHONG viet lai) tim dieu khoan LIEN QUAN NHAT trong tap doi chieu
     (cac van ban PHAP LY BEN NGOAI cung mien, hoac van ban NOI BO khac).
  3. Dong goi Evidence Package (chunk A = noi bo, chunk B = doi chieu) kem
     citation THAT tu dataset.
  4. Phan loai xung dot:
     a) RULE-BASED (luon chay, khong can LLM): trich xuat nguong so (floor %,
        ceiling %, ceiling ty dong) tren CA HAI phia bang regex tai su dung
        tu buoi_17/scripts/compliance_gap.py. Neu tim duoc va SO SANH duoc:
          - noi bo LONG HON/VUOT muc phap luat cho phep -> XUNG_DOT
            (Han muc/nguong), severity HIGH.
          - noi bo CHAT HON hoac BANG -> KHONG_XUNG_DOT (khong phai vi pham,
            chi la quy dinh rieng chat hon).
     b) LLM-ASSISTED (tuy chon, chi khi co GEMINI_API_KEY va khong co bang
        chung so o (a)): goi Gemini VOI DUY NHAT 2 doan van ban that, yeu cau
        tra ve JSON co cau truc, KHONG duoc bia dieu khoan/tu suy dien ngoai
        context. Neu LLM tra ve "khong du can cu" hoac loi -> giu
        CHUA_DU_BANG_CHUNG.
     c) Neu khong co nguong so VA khong co LLM (hoac LLM khong ket luan) ->
        CHUA_DU_BANG_CHUNG (KHONG tu bia xung dot chi vi trung tu khoa).
  5. review_status = "NEEDS_HUMAN_REVIEW" cho MOI dong (khong chi cac dong co
     xung dot) - dung nguyen tac cua bai: AI Compliance Checker khong phai
     ket luan kiem toan cuoi cung.
  6. Ghi AuditLogger (tai su dung buoi_17/scripts/audit_logger.py).

Xuat: outputs/compliance_conflicts.csv, outputs/compliance_conflict_report.md
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from rank_bm25 import BM25Okapi

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
BUOI17_SCRIPTS = (BASE_DIR / "../buoi_17/scripts").resolve()
sys.path.insert(0, str(BUOI14_DIR))
sys.path.insert(0, str(BUOI17_SCRIPTS))

from src.bm25_retriever import tokenize  # noqa: E402  (TAI SU DUNG, khong viet lai)
import audit_logger  # noqa: E402  (TAI SU DUNG nguyen ban tu buoi_17)

# audit_logger.py mac dinh ghi log vao buoi_17/outputs/ (vi __file__ nam trong
# buoi_17/scripts/). Buoi 18 tai su dung LOGIC (log_event/_redact/read_events)
# nguyen ven nhung ghi vao outputs/ CUA CHINH buoi_18 - chi doi lai duong dan
# module-level LOG_PATH, khong sua logic ben trong.
audit_logger.LOG_PATH = BASE_DIR / "outputs" / "audit_log.jsonl"

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
OUT_CSV = BASE_DIR / "outputs" / "compliance_conflicts.csv"
OUT_MD = BASE_DIR / "outputs" / "compliance_conflict_report.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_catalog_b18 import DOMAIN_MAP  # noqa: E402  (tai su dung anh xa domain PROMPT 1)

# --- Regex nguong so - TAI SU DUNG NGUYEN VEN tu buoi_17/scripts/compliance_gap.py ---
FLOOR_PATTERN = re.compile(
    r"(tối thiểu|không thấp hơn|ít nhất)\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
CEILING_PCT_PATTERN = re.compile(
    r"(tối đa|không quá|không vượt quá)\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
CEILING_AMOUNT_PATTERN = re.compile(
    r"(tối đa|không quá|không vượt quá)\s+(\d+(?:[.,]\d+)?)\s*tỷ", re.IGNORECASE
)

CONFLICT_TYPES = ["Hạn mức/ngưỡng", "Quy trình thực hiện", "Thẩm quyền phê duyệt", "Thời hạn/hiệu lực", "Khác"]
SEVERITIES = ["HIGH", "MEDIUM", "LOW"]


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _parse_roles(raw) -> list[str]:
    if pd.isna(raw):
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else [str(v)]
    except Exception:  # noqa: BLE001
        return [r.strip() for r in str(raw).split(",") if r.strip()]


def rbac_filter(df: pd.DataFrame, user_role: str | None) -> pd.DataFrame:
    """Loc TRUOC retrieval theo allowed_roles - fail-closed: chunk khong xac
    dinh duoc allowed_roles se KHONG duoc xem (giong nguyen tac buoi_14/17)."""
    if not user_role:
        return df
    mask = df["allowed_roles"].apply(lambda r: user_role in _parse_roles(r))
    return df[mask].reset_index(drop=True)


def build_external_index(df: pd.DataFrame):
    external = df[~df["document_id"].astype(str).str.startswith("agr_")].reset_index(drop=True)
    corpus_tokens = [tokenize(t) for t in external["text"].fillna("")]
    bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None
    return external, bm25


def best_external_match(query_text: str, external: pd.DataFrame, bm25) -> tuple[dict | None, float]:
    if bm25 is None or not len(external):
        return None, 0.0
    scores = bm25.get_scores(tokenize(query_text))
    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])
    if best_score <= 0:
        return None, 0.0
    return external.iloc[best_idx].to_dict(), best_score


def _rule_based_numeric_check(text_a: str, text_b: str) -> dict | None:
    """So sanh nguong so (%) hoac han muc (ty dong) tren CA HAI phia. text_a
    = noi bo, text_b = doi chieu (phap luat/van ban khac). Tra ve None neu
    khong tim duoc cap nguong cung loai tren ca hai phia."""
    a_floor, b_floor = FLOOR_PATTERN.search(text_a), FLOOR_PATTERN.search(text_b)
    if a_floor and b_floor:
        a_val, b_val = _num(a_floor.group(2)), _num(b_floor.group(2))
        if a_val < b_val:
            return {
                "classification": "XUNG_DOT", "conflict_type": "Hạn mức/ngưỡng", "severity": "HIGH",
                "description": (
                    f"Văn bản đối chiếu yêu cầu tối thiểu {b_val}%, nhưng nội bộ chỉ quy định tối thiểu "
                    f"{a_val}% ({a_val}% < {b_val}%) — THẤP HƠN mức pháp luật yêu cầu, có rủi ro vi phạm."
                ),
                "method": "rule_numeric_floor_pct", "confidence": 0.85,
            }
        return {
            "classification": "KHONG_XUNG_DOT", "conflict_type": None, "severity": None,
            "description": (
                f"Văn bản đối chiếu yêu cầu tối thiểu {b_val}%, nội bộ quy định tối thiểu {a_val}% "
                f"(≥ yêu cầu) — không xung đột, nội bộ đáp ứng/chặt hơn."
            ),
            "method": "rule_numeric_floor_pct", "confidence": 0.85,
        }

    a_ceil, b_ceil = CEILING_PCT_PATTERN.search(text_a), CEILING_PCT_PATTERN.search(text_b)
    if a_ceil and b_ceil:
        a_val, b_val = _num(a_ceil.group(2)), _num(b_ceil.group(2))
        if a_val > b_val:
            return {
                "classification": "XUNG_DOT", "conflict_type": "Hạn mức/ngưỡng", "severity": "HIGH",
                "description": f"Nội bộ cho phép tối đa {a_val}%, vượt trần {b_val}% của văn bản đối chiếu.",
                "method": "rule_numeric_ceiling_pct", "confidence": 0.8,
            }
        return {
            "classification": "KHONG_XUNG_DOT", "conflict_type": None, "severity": None,
            "description": f"Nội bộ tối đa {a_val}% (≤ trần {b_val}%) — không xung đột.",
            "method": "rule_numeric_ceiling_pct", "confidence": 0.8,
        }

    a_amt, b_amt = CEILING_AMOUNT_PATTERN.search(text_a), CEILING_AMOUNT_PATTERN.search(text_b)
    if a_amt and b_amt:
        a_val, b_val = _num(a_amt.group(2)), _num(b_amt.group(2))
        if a_val > b_val:
            return {
                "classification": "XUNG_DOT", "conflict_type": "Hạn mức/ngưỡng", "severity": "HIGH",
                "description": f"Nội bộ cho phép tối đa {a_val} tỷ, vượt trần {b_val} tỷ của văn bản đối chiếu.",
                "method": "rule_numeric_ceiling_amount", "confidence": 0.8,
            }
        return {
            "classification": "KHONG_XUNG_DOT", "conflict_type": None, "severity": None,
            "description": f"Nội bộ tối đa {a_val} tỷ (≤ trần {b_val} tỷ) — không xung đột.",
            "method": "rule_numeric_ceiling_amount", "confidence": 0.8,
        }

    return None


def llm_refine_conflict(citation_a: str, text_a: str, citation_b: str, text_b: str) -> dict | None:
    """Tuy chon: goi Gemini CHI voi 2 doan van ban that. Tra ve None neu
    khong co key/loi -> giu CHUA_DU_BANG_CHUNG, KHONG bao gio tu bia."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            "Bạn là trợ lý kiểm toán tuân thủ ngân hàng. So sánh CHÉO hai đoạn văn bản dưới đây "
            "(A = quy định nội bộ Agribank, B = văn bản đối chiếu). CHỈ dựa vào đúng 2 đoạn này, "
            "KHÔNG dùng kiến thức ngoài, KHÔNG suy diễn hay bịa nội dung không có trong văn bản.\n\n"
            f"VĂN BẢN A ({citation_a}):\n{text_a}\n\nVĂN BẢN B ({citation_b}):\n{text_b}\n\n"
            "Trả lời DUY NHẤT một JSON object với các trường:\n"
            '{"has_conflict": true/false, '
            f'"conflict_type": một trong {CONFLICT_TYPES} hoặc null, '
            f'"severity": một trong {SEVERITIES} hoặc null, '
            '"description": mô tả ngắn gọn bằng tiếng Việt trích dẫn cụ thể từ A và B, '
            '"confident": true/false (false nếu không đủ căn cứ để kết luận)}\n'
            "Nếu hai văn bản không đủ liên quan hoặc không đủ căn cứ, đặt confident=false và "
            "has_conflict=false."
        )
        model = os.environ.get("LLM_MODEL", "gemini-3.6-flash")
        resp = client.models.generate_content(model=model, contents=prompt)
        raw = (resp.text or "").strip()
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
        if not data.get("confident", True):
            return None
        if data.get("has_conflict"):
            ctype = data.get("conflict_type") if data.get("conflict_type") in CONFLICT_TYPES else "Khác"
            sev = data.get("severity") if data.get("severity") in SEVERITIES else "MEDIUM"
            return {
                "classification": "XUNG_DOT", "conflict_type": ctype, "severity": sev,
                "description": str(data.get("description", "")).strip(),
                "method": "llm_assisted", "confidence": 0.7,
            }
        return {
            "classification": "KHONG_XUNG_DOT", "conflict_type": None, "severity": None,
            "description": str(data.get("description", "Không phát hiện xung đột theo phân tích LLM.")).strip(),
            "method": "llm_assisted", "confidence": 0.7,
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[CANH BAO] LLM refine that bai ({type(exc).__name__}: {exc}). Giu CHUA_DU_BANG_CHUNG.",
              file=sys.stderr)
        return None


def classify_conflict(internal_row: dict, external_row: dict | None, score: float, use_llm: bool) -> dict:
    if external_row is None:
        return {
            "classification": "CHUA_DU_BANG_CHUNG", "conflict_type": None, "severity": None,
            "description": "Không tìm thấy văn bản đối chiếu liên quan (BM25 score=0) — không đủ căn cứ để kết luận.",
            "method": "no_candidate", "confidence": 0.3,
        }
    text_a = str(internal_row.get("text", ""))
    text_b = str(external_row.get("text", ""))

    numeric = _rule_based_numeric_check(text_a, text_b)
    if numeric is not None:
        return numeric

    if use_llm:
        llm_result = llm_refine_conflict(
            internal_row.get("citation", ""), text_a, external_row.get("citation", ""), text_b
        )
        if llm_result is not None:
            return llm_result

    return {
        "classification": "CHUA_DU_BANG_CHUNG", "conflict_type": None, "severity": None,
        "description": (
            f"Có văn bản đối chiếu liên quan (BM25 score={score:.1f}) nhưng không trích xuất được "
            "ngưỡng số kiểm chứng được trên cả hai phía, và không có LLM xác nhận đủ căn cứ. "
            "Cần kiểm toán viên đọc trực tiếp cả hai văn bản để kết luận."
        ),
        "method": "rule_no_confident_match", "confidence": 0.35,
    }


def run_compliance_check(
    internal_document_ids: list[str] | None = None,
    user_role: str | None = None,
    user_id: str = "system",
    use_llm: bool = True,
    max_llm_calls: int = 20,
) -> pd.DataFrame:
    df = pd.read_csv(COMBINED_CSV)
    internal_all = df[df["document_id"].astype(str).str.startswith("agr_")].reset_index(drop=True)
    internal_all = rbac_filter(internal_all, user_role)

    if internal_document_ids:
        internal_all = internal_all[internal_all["document_id"].isin(internal_document_ids)].reset_index(drop=True)

    external, bm25 = build_external_index(df)

    rows = []
    llm_calls_used = 0
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    for _, irow in internal_all.iterrows():
        irow = irow.to_dict()
        erow, score = best_external_match(irow["text"], external, bm25)
        allow_llm = use_llm and llm_calls_used < max_llm_calls
        result = classify_conflict(irow, erow, score, use_llm=allow_llm)
        if result.get("method") == "llm_assisted":
            llm_calls_used += 1

        domain = DOMAIN_MAP.get(irow["document_id"], {}).get("domain", "CHƯA PHÂN LOẠI")
        rows.append({
            "conflict_id": f"CFT_{uuid.uuid4().hex[:10]}",
            "domain": domain,
            "doc_a_id": irow["document_id"],
            "doc_a_citation": irow.get("citation", ""),
            "doc_a_text": irow.get("text", ""),
            "doc_b_id": erow.get("document_id") if erow else None,
            "doc_b_citation": erow.get("citation") if erow else None,
            "doc_b_text": erow.get("text") if erow else None,
            "classification": result["classification"],
            "conflict_type": result["conflict_type"],
            "severity": result["severity"],
            "description": result["description"],
            "classification_method": result["method"],
            "confidence": result["confidence"],
            "bm25_score": round(score, 2),
            "review_status": "NEEDS_HUMAN_REVIEW",
            "timestamp": now,
            "request_id": request_id,
        })

    out_df = pd.DataFrame(rows)

    audit_logger.log_event(
        user_id=user_id, user_role=[user_role] if user_role else ["Admin"],
        action="compliance_check_uc3", query=f"domains={internal_document_ids or 'ALL'}",
        retrieval_method="bm25_cross_comparison",
        retrieved_document_ids=out_df["doc_b_id"].dropna().unique().tolist() if len(out_df) else [],
        n_rejected_by_rbac=0, status="SUCCESS",
        extra={
            "n_pairs_evaluated": len(out_df),
            "n_conflicts": int((out_df["classification"] == "XUNG_DOT").sum()) if len(out_df) else 0,
            "llm_calls_used": llm_calls_used,
        },
    )
    return out_df


def main() -> None:
    # Demo: 3 mien nghiep vu theo dung yeu cau cua bai (Kho quy, CAR, Tin dung).
    # Voi moi mien, lay CAP DAI DIEN (chunk noi bo co diem BM25 doi chieu cao
    # nhat trong mien do) de bao cao ro rang; engine van cham HET cac chunk
    # cua 3 van ban nay (khong chi 1 chunk/mien) - xem toan bo trong CSV.
    demo_doc_ids = ["agr_at01", "agr_car02", "agr_td03"]
    df = run_compliance_check(internal_document_ids=demo_doc_ids, user_role="Admin", user_id="demo_uc3")

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    lines = ["# Buổi 18 — Compliance Conflict Report (PROMPT 2 / UC3)\n"]
    lines.append(f"Số cặp đã đối chiếu: **{len(df)}** (3 miền demo: Kho quỹ, CAR, Tín dụng)\n")

    lines.append("## Phân bố classification\n")
    lines.append("| Classification | Số lượng |")
    lines.append("|---|---|")
    for cls, cnt in df["classification"].value_counts().items():
        lines.append(f"| {cls} | {cnt} |")
    lines.append("")

    conflicts = df[df["classification"] == "XUNG_DOT"]
    lines.append(f"## Xung đột phát hiện được: {len(conflicts)}\n")
    for _, r in conflicts.iterrows():
        lines.append(f"### {r['domain']} — {r['conflict_type']} (Severity: {r['severity']})\n")
        lines.append(f"- **Văn bản A (nội bộ)**: `{r['doc_a_citation']}`")
        lines.append(f"- **Văn bản B (đối chiếu)**: `{r['doc_b_citation']}`")
        lines.append(f"- **Mô tả**: {r['description']}")
        lines.append(f"- **Phương pháp**: {r['classification_method']} | review_status: {r['review_status']}\n")

    non_conflicts = df[df["classification"] != "XUNG_DOT"]
    lines.append(f"## Các cặp KHÔNG xung đột / chưa đủ bằng chứng: {len(non_conflicts)}\n")
    lines.append("| Domain | Văn bản A | Văn bản B | Classification | Ghi chú |")
    lines.append("|---|---|---|---|---|")
    for _, r in non_conflicts.iterrows():
        b_cite = r["doc_b_citation"] or "(không tìm thấy)"
        lines.append(f"| {r['domain']} | {r['doc_a_citation']} | {b_cite} | {r['classification']} | {r['description'][:100]} |")
    lines.append("")

    all_citation_ok = df["doc_a_citation"].notna().all() and (
        (df["classification"] != "XUNG_DOT") | df["doc_b_citation"].notna()
    ).all()
    all_review_ok = (df["review_status"] == "NEEDS_HUMAN_REVIEW").all()

    lines.append("## Kết luận\n")
    lines.append(f"COMPLIANCE CHECKER ENGINE: {'PASS' if len(df) > 0 and all_citation_ok else 'FAIL'}")
    lines.append(f"CONFLICTS DETECTED: {len(conflicts)}")
    lines.append(f"HUMAN REVIEW GUARDRAIL: {'PASS' if all_review_ok else 'FAIL'}")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT_CSV}")
    print(f"Da ghi {OUT_MD}")
    print("\n".join(lines[-3:]))


if __name__ == "__main__":
    main()
