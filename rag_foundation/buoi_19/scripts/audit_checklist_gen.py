"""
BUOI 19 - PROMPT 2: UC4 - AI Audit Checklist Generator, PHIEN BAN
DUAL-PROVIDER (Ollama local / Gemini cloud).

Ban CAP NHAT cua buoi_18/scripts/audit_checklist_gen.py - GIU NGUYEN 100%
RBAC fail-closed, BM25 (tai su dung tu compliance_checker.py CUA CHINH
BUOI 19, da tro thanh dual-provider), co che fail-closed neo bang chunk_id
(khong tin LLM mu quang, luon lay citation THAT tu du lieu). CHI THAY doi noi
goi LLM sang `llm_provider.call_llm()`. buoi_18/scripts/audit_checklist_gen.py
GIU NGUYEN, KHONG bi sua.

Xuat: outputs/audit_checklist_results.csv, outputs/audit_checklist_report.md
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
BUOI17_SCRIPTS = (BASE_DIR / "../buoi_17/scripts").resolve()
BUOI18_SCRIPTS = (BASE_DIR / "../buoi_18/scripts").resolve()
sys.path.insert(0, str(BUOI14_DIR))
sys.path.insert(0, str(BUOI17_SCRIPTS))
sys.path.insert(0, str(BUOI18_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.bm25_retriever import tokenize  # noqa: E402
import audit_logger  # noqa: E402
from llm_provider import call_llm  # noqa: E402
from data_catalog_b18 import DOMAIN_MAP  # noqa: E402  (TAI SU DUNG nguyen ban tu buoi_18)
from compliance_checker import rbac_filter, build_external_index  # noqa: E402  (dung ban dual-provider CUA BUOI 19)

audit_logger.LOG_PATH = BASE_DIR / "outputs" / "audit_log.jsonl"

_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

COMBINED_CSV = BASE_DIR / os.environ["SOURCE_COMBINED_SECURE_CSV"]
OUT_CSV = BASE_DIR / "outputs" / "audit_checklist_results.csv"
OUT_MD = BASE_DIR / "outputs" / "audit_checklist_report.md"

HIGH_RISK_WORDS = ["nghiêm cấm", "không được", "bắt buộc", "tuyệt đối", "tối thiểu", "an toàn tuyệt đối"]
MEDIUM_RISK_WORDS = ["phải", "chịu trách nhiệm", "định kỳ", "báo cáo"]


def _domain_doc_ids(domain: str) -> list[str]:
    return [doc_id for doc_id, meta in DOMAIN_MAP.items() if meta["domain"] == domain]


def _domain_code(domain: str) -> str:
    for meta in DOMAIN_MAP.values():
        if meta["domain"] == domain:
            return meta["code"]
    return "GEN"


def _heuristic_risk_level(text: str) -> str:
    low = text.lower()
    if any(w in low for w in HIGH_RISK_WORDS):
        return "HIGH"
    if any(w in low for w in MEDIUM_RISK_WORDS):
        return "MEDIUM"
    return "LOW"


def _gather_context(domain: str, user_role: str | None, top_external: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(COMBINED_CSV)
    df = rbac_filter(df, user_role)

    doc_ids = _domain_doc_ids(domain)
    if not doc_ids:
        # Domain khong ton tai trong DOMAIN_MAP -> tra ve RONG, KHONG fallback
        # sang dung chuoi domain lam BM25 query (Unknown Domain Test).
        empty = df.iloc[0:0]
        return empty, empty

    internal_chunks = df[df["document_id"].isin(doc_ids)].reset_index(drop=True)

    external, bm25 = build_external_index(df)
    domain_text = " ".join(internal_chunks["text"].fillna("").tolist()) if len(internal_chunks) else domain
    if bm25 is not None and len(external) and domain_text.strip():
        scores = bm25.get_scores(tokenize(domain_text))
        top_idx = scores.argsort()[::-1][:top_external]
        top_idx = [i for i in top_idx if scores[i] > 0]
        external_chunks = external.iloc[top_idx].reset_index(drop=True)
    else:
        external_chunks = external.iloc[0:0]

    return internal_chunks, external_chunks


def _extractive_checklist(domain: str, unit: str, internal_chunks: pd.DataFrame, external_chunks: pd.DataFrame) -> list[dict]:
    """Fallback khong dung LLM: moi chunk lien quan -> 1 muc checklist bam
    sat NGUYEN VAN, khong dien giai sang y ngoai chunk."""
    code = _domain_code(domain)
    items = []
    seq = 1
    for _, r in pd.concat([internal_chunks, external_chunks], ignore_index=True).iterrows():
        text = str(r["text"]).strip()
        snippet = text[:220].rstrip()
        question = f"Đơn vị có tuân thủ đúng nội dung sau tại {r.get('article', '(không rõ điều khoản)')} không? \"{snippet}{'...' if len(text) > 220 else ''}\""
        risk_level = _heuristic_risk_level(text)
        risk_desc = (
            f"Vi phạm nội dung tại {r.get('citation', '')} có thể dẫn tới rủi ro tuân thủ/vận hành "
            f"tương ứng mức {risk_level.lower()} theo cụm từ bắt buộc trong chính văn bản."
        )
        items.append({
            "item_id": f"CHK_{code}_{seq:02d}",
            "domain": domain,
            "unit_scope": unit,
            "audit_question": question,
            "risk_description": risk_desc,
            "risk_level": risk_level,
            "source_citation": r.get("citation", ""),
            "recommendation": "Đối chiếu hồ sơ/thực tế tại đơn vị với đúng yêu cầu nêu trên; lập biên bản và báo cáo nếu phát hiện sai lệch.",
            "review_status": "NEEDS_HUMAN_REVIEW",
            "generation_method": "extractive_rule_based",
        })
        seq += 1
    return items


def _llm_checklist(domain: str, unit: str, internal_chunks: pd.DataFrame, external_chunks: pd.DataFrame) -> list[dict] | None:
    context_rows = pd.concat([internal_chunks, external_chunks], ignore_index=True)
    if not len(context_rows):
        return None
    # Neo bang chunk_id (ma ky thuat ngan) - CHI chap nhan khi chunk_id do
    # THAT SU ton tai trong context -> luon tra ve citation GOC tu du lieu
    # that, khong bao gio dung nguyen van chuoi LLM tra ve lam ket qua cuoi.
    citation_by_chunk_id = {str(r["chunk_id"]): str(r["citation"]) for _, r in context_rows.iterrows()}
    context_block = "\n\n".join(
        f"[chunk_id: {r['chunk_id']}]\n{r['text']}" for _, r in context_rows.iterrows()
    )

    prompt = (
        "Bạn là trợ lý kiểm toán nội bộ ngân hàng. Dựa DUY NHẤT vào CONTEXT dưới đây (các điều "
        "khoản quy định nội bộ Agribank và văn bản pháp luật liên quan), hãy sinh danh mục "
        "checklist kiểm toán cho:\n"
        f"- Domain (miền nghiệp vụ): {domain}\n- Unit (đơn vị được kiểm toán): {unit}\n\n"
        f"CONTEXT (mỗi đoạn có mã chunk_id riêng ở đầu):\n{context_block}\n\n"
        "KHÔNG được bịa điều khoản/văn bản không có trong CONTEXT. Mỗi mục PHẢI có source_chunk_id "
        "là ĐÚNG một trong các mã chunk_id xuất hiện ở CONTEXT (chép chính xác, không thêm bớt ký tự).\n\n"
        "Trả lời DUY NHẤT một JSON array, mỗi phần tử có các trường: "
        'audit_question (câu hỏi kiểm toán cụ thể), risk_description (rủi ro nếu vi phạm), '
        'risk_level ("HIGH"/"MEDIUM"/"LOW"), source_chunk_id (mã chunk_id đúng như trong CONTEXT), '
        'recommendation (gợi ý hành động kiểm toán cụ thể).'
    )
    raw = call_llm(prompt, format_json=True)
    if not raw:
        return None

    try:
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
        # Mot so model nho (Qwen3:0.6b) doi khi boc mang trong {"items": [...]}
        # thay vi mang thuan tuy du da yeu cau ro - chap nhan ca hai dang de
        # khong loai bo oan ket qua hop le, KHONG noi long dieu kien fail-closed
        # ve citation ben duoi.
        if isinstance(data, dict):
            for key in ("items", "checklist", "results"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            return None

        provider = os.environ.get("LLM_PROVIDER", "ollama")
        code = _domain_code(domain)
        items = []
        dropped = 0
        seq = 1
        for entry in data:
            if not isinstance(entry, dict):
                dropped += 1
                continue
            raw_chunk_id = str(entry.get("source_chunk_id", "")).strip()
            citation = citation_by_chunk_id.get(raw_chunk_id)
            if citation is None:
                m = re.search(r"([A-Za-z0-9_]+)\s*\]?\s*$", raw_chunk_id)
                if m:
                    citation = citation_by_chunk_id.get(m.group(1))
            if citation is None:
                # fail-closed THAT SU: khong tim duoc chunk_id nao khop du
                # lieu that -> loai bo muc nay, KHONG bia.
                dropped += 1
                continue
            risk_level = entry.get("risk_level") if entry.get("risk_level") in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
            items.append({
                "item_id": f"CHK_{code}_{seq:02d}",
                "domain": domain,
                "unit_scope": unit,
                "audit_question": str(entry.get("audit_question", "")).strip(),
                "risk_description": str(entry.get("risk_description", "")).strip(),
                "risk_level": risk_level,
                "source_citation": citation,
                "recommendation": str(entry.get("recommendation", "")).strip(),
                "review_status": "NEEDS_HUMAN_REVIEW",
                "generation_method": f"llm_assisted_{provider}",
            })
            seq += 1
        if dropped:
            print(f"[CANH BAO] LLM tra ve {len(data)} muc, {dropped} muc bi loai vi citation khong khop "
                  "du lieu that (fail-closed, khong bia).", file=sys.stderr)
        return items if items else None
    except Exception as exc:  # noqa: BLE001
        print(f"[CANH BAO] LLM checklist that bai/du lieu khong hop le ({type(exc).__name__}: {exc}). "
              "Chuyen sang extractive.", file=sys.stderr)
        return None


def generate_checklist(domain: str, unit: str, user_role: str | None = None, user_id: str = "system") -> list[dict]:
    internal_chunks, external_chunks = _gather_context(domain, user_role)

    if not len(internal_chunks) and not len(external_chunks):
        audit_logger.log_event(
            user_id=user_id, user_role=[user_role] if user_role else ["Admin"],
            action="audit_checklist_gen_uc4", query=f"domain={domain} unit={unit}",
            status="DENIED" if user_role else "ERROR",
            extra={"reason": "Chưa có dữ liệu quy định cho domain này (hoặc bị RBAC chặn hết)."},
        )
        return []

    items = _llm_checklist(domain, unit, internal_chunks, external_chunks)
    used_llm = items is not None
    if not used_llm:
        items = _extractive_checklist(domain, unit, internal_chunks, external_chunks)

    audit_logger.log_event(
        user_id=user_id, user_role=[user_role] if user_role else ["Admin"],
        action="audit_checklist_gen_uc4", query=f"domain={domain} unit={unit}",
        retrieval_method="bm25+rbac",
        retrieved_document_ids=list(pd.concat([internal_chunks, external_chunks])["document_id"].unique()),
        citation_ids=[it["source_citation"] for it in items],
        status="SUCCESS",
        extra={
            "generation_method": items[0]["generation_method"] if items else ("llm_assisted" if used_llm else "extractive_rule_based"),
            "n_items": len(items),
            "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
        },
    )
    return items


def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    demo_cases = [
        ("An toàn kho quỹ & Vận chuyển tiền", "Chi nhánh loại 1"),
        ("Bảo mật CNTT & AI", "Khối CNTT"),
    ]

    all_items = []
    for domain, unit in demo_cases:
        all_items.extend(generate_checklist(domain, unit, user_role="Admin", user_id="demo_uc4"))

    out_df = pd.DataFrame(all_items)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    lines = [f"# Buổi 19 — Audit Checklist Report (PROMPT 2 / UC4, provider={provider})\n"]
    lines.append(f"Số mục checklist đã sinh: **{len(out_df)}** (demo 2 domain: An toàn kho quỹ, Bảo mật CNTT & AI)\n")

    for domain, unit in demo_cases:
        sub = out_df[(out_df["domain"] == domain) & (out_df["unit_scope"] == unit)] if len(out_df) else out_df
        lines.append(f"## {domain} — Unit: {unit} ({len(sub)} mục)\n")
        lines.append("| Mã mục | Câu hỏi kiểm toán | Mức rủi ro | Citation | Khuyến nghị |")
        lines.append("|---|---|---|---|---|")
        for _, r in sub.iterrows():
            q = r["audit_question"][:110] + ("..." if len(r["audit_question"]) > 110 else "")
            rec = r["recommendation"][:80] + ("..." if len(r["recommendation"]) > 80 else "")
            lines.append(f"| {r['item_id']} | {q} | {r['risk_level']} | `{r['source_citation']}` | {rec} |")
        lines.append("")

    citations_attached = len(out_df) > 0 and out_df["source_citation"].astype(str).str.strip().ne("").all()
    generator_ok = len(out_df) > 0 and citations_attached

    lines.append("## Kết luận\n")
    lines.append(f"LLM_PROVIDER: {provider}")
    lines.append(f"CHECKLIST GENERATOR ENGINE: {'PASS' if generator_ok else 'FAIL'}")
    lines.append(f"CHECKLIST ITEMS GENERATED: {len(out_df)}")
    lines.append(f"CITATIONS ATTACHED: {'YES' if citations_attached else 'NO'}")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT_CSV}")
    print(f"Da ghi {OUT_MD}")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
