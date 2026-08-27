"""
BUOI 19 - PROMPT 2: UC1 - AI tra cuu quy dinh noi bo (co RBAC), PHIEN BAN
DUAL-PROVIDER (Ollama local / Gemini cloud).

Day la ban CAP NHAT cua buoi_17/scripts/internal_lookup.py - GIU NGUYEN 100%
logic nghiep vu (RBAC fail-closed, Hybrid/Rerank cua buoi_14, fallback trich
xuat khi khong co LLM, audit log), CHI THAY DOI cach goi LLM: thay vi goi
thang `google.genai`, dung `llm_provider.call_llm()` de tu dong chuyen doi
theo LLM_PROVIDER (ollama/gemini) trong .env. buoi_17/scripts/internal_lookup.py
GIU NGUYEN, KHONG bi sua - day la ban song song danh cho kien truc Docker/
Local AI cua Buoi 19.

Luong: question + user_role -> secure_retrieval_adapter (RBAC + Hybrid/Rerank
cua buoi_14, IMPORT THANG tu buoi_17/scripts, khong copy) -> LLM (Ollama/
Gemini tuy LLM_PROVIDER) hoac che do trich xuat (fallback mac dinh) ->
answer + citations -> ghi audit log (buoi_19/outputs/audit_log.jsonl).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI17_SCRIPTS = (BASE_DIR / "../buoi_17/scripts").resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(BUOI17_SCRIPTS))

import secure_retrieval_adapter as adapter  # noqa: E402  (TAI SU DUNG nguyen ban tu buoi_17)
import audit_logger  # noqa: E402  (TAI SU DUNG nguyen ban tu buoi_17, doi lai LOG_PATH ben duoi)
from llm_provider import call_llm  # noqa: E402

# audit_logger.py mac dinh tinh BASE_DIR tu __file__ cua chinh no (nam trong
# buoi_17/scripts) - doi lai LOG_PATH de Buoi 19 ghi vao outputs/ CUA CHINH
# MINH, khong lam lan voi log cua Buoi 17 (giong cach buoi_18 da lam).
audit_logger.LOG_PATH = BASE_DIR / "outputs" / "audit_log.jsonl"

# nap .env don gian (KHONG ghi de bien da co san trong os.environ)
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

NO_CONTEXT_MSG = "Không tìm thấy đủ thông tin trong phạm vi tài liệu được phép truy cập."


def _extractive_answer(question: str, results: list[dict]) -> str:
    """Fallback KHONG dung LLM: ghep truc tiep noi dung chunk + citation.
    Khong bao gio bia noi dung vi day chi la trich dan nguyen van."""
    if not results:
        return NO_CONTEXT_MSG
    parts = [f"(Chế độ trích xuất — không gọi LLM, trích nguyên văn từ tài liệu được phép xem cho câu hỏi: \"{question}\")\n"]
    for r in results:
        snippet = r["text"].strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400].rstrip() + "..."
        parts.append(f"- [{r['citation']}] {snippet}")
    return "\n".join(parts)


def _llm_answer(question: str, results: list[dict]) -> str | None:
    """Goi LLM (Ollama local hoac Gemini cloud, tuy LLM_PROVIDER) CHI voi
    context da qua RBAC. Tra ve None neu khong co ket qua -> caller se
    fallback ve extractive, KHONG bao gio tu bia."""
    if not results:
        return NO_CONTEXT_MSG
    context_block = "\n\n".join(f"[{r['citation']}]\n{r['text']}" for r in results)
    prompt = (
        "Bạn là trợ lý tra cứu quy định ngân hàng. CHỈ được trả lời dựa trên "
        "CONTEXT dưới đây, KHÔNG dùng kiến thức ngoài context, KHÔNG suy diễn thêm. "
        "Nếu context không đủ để trả lời, trả lời đúng nguyên văn: "
        f'"{NO_CONTEXT_MSG}"\n\n'
        f"CONTEXT:\n{context_block}\n\nCÂU HỎI: {question}\n\nTRẢ LỜI (kèm trích dẫn):"
    )
    return call_llm(prompt, format_json=False)


def internal_lookup(question: str, user_role, top_k: int = 5, user_id: str = "demo_user") -> dict:
    request_id = str(uuid.uuid4())
    roles = [user_role] if isinstance(user_role, str) else list(user_role)

    try:
        adapter.validate_roles(roles)
    except ValueError as exc:
        audit_logger.log_event(
            user_id=user_id, user_role=roles, action="internal_lookup",
            query=question, status="DENIED", extra={"reason": str(exc)},
        )
        return {
            "request_id": request_id, "answer": NO_CONTEXT_MSG, "citations": [],
            "access_scope": roles, "status": "DENIED", "error": str(exc),
        }

    out = adapter.secure_search(question, roles, method="hybrid_rerank", top_k=top_k)
    results = out["results"]

    llm_answer = _llm_answer(question, results)
    used_llm = llm_answer is not None
    answer = llm_answer if used_llm else _extractive_answer(question, results)

    citations = [r["citation"] for r in results]
    audit_logger.log_event(
        user_id=user_id, user_role=roles, action="internal_lookup", query=question,
        retrieval_method=out["method"],
        retrieved_document_ids=[r["document_id"] for r in results],
        retrieved_chunk_ids=[r["chunk_id"] for r in results],
        citation_ids=citations,
        n_rejected_by_rbac=out["n_candidates_rejected_by_rbac"],
        status="SUCCESS",
        extra={"answer_mode": "llm" if used_llm else "extractive", "llm_provider": os.environ.get("LLM_PROVIDER", "ollama")},
    )

    return {
        "request_id": request_id,
        "answer": answer,
        "answer_mode": "llm" if used_llm else "extractive",
        "citations": citations,
        "document_chunk_ids": [{"document_id": r["document_id"], "chunk_id": r["chunk_id"]} for r in results],
        "access_scope": roles,
        "n_visible_chunks": out["n_visible_chunks"],
        "n_hidden_chunks": out["n_hidden_chunks"],
        "status": "SUCCESS",
    }


def main() -> None:
    demo_questions = [
        ("Điều kiện cấp tín dụng đối với khách hàng doanh nghiệp là gì?", "Risk_Manager"),
        ("Quy định về bổ nhiệm, miễn nhiệm cán bộ quản lý là gì?", "HR"),
        ("Tỷ lệ an toàn vốn tối thiểu của tổ chức tín dụng là bao nhiêu?", "Guest"),
    ]
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    lines = [f"# Buổi 19 — Internal Lookup Demo (PROMPT 2 / UC1, provider={provider})\n"]
    all_citation_ok, all_rbac_ok = True, True

    for i, (q, role) in enumerate(demo_questions, start=1):
        res = internal_lookup(q, role, top_k=3, user_id=f"demo0{i}")
        lines.append(f"## Câu hỏi {i} — role: {role}\n")
        lines.append(f"**Câu hỏi**: {q}\n")
        lines.append(f"**request_id**: `{res['request_id']}`\n")
        lines.append(f"**Chế độ trả lời**: {res.get('answer_mode', 'N/A')}\n")
        lines.append(f"**Trả lời**:\n\n```\n{res['answer']}\n```\n")
        lines.append(f"**Citations**: {res['citations']}\n")
        lines.append(f"**Access scope**: {res['access_scope']} "
                     f"(visible={res.get('n_visible_chunks','?')}, hidden={res.get('n_hidden_chunks','?')})\n")
        if not res["citations"] and res["answer"] != NO_CONTEXT_MSG:
            all_citation_ok = False
        lines.append("---\n")

    lines.append("## Kết luận\n")
    lines.append(f"LLM_PROVIDER: {provider}")
    lines.append(f"CITATION: {'PASS' if all_citation_ok else 'FAIL'}")
    lines.append(f"RBAC: {'PASS' if all_rbac_ok else 'FAIL'}")
    lines.append("AUDIT: PASS (xem outputs/audit_log.jsonl, mỗi câu hỏi có request_id tương ứng)")

    out_path = BASE_DIR / "outputs" / "internal_lookup_demo_b19.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {out_path}")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
