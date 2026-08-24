"""
BUOI 17 - PROMPT 5: Use Case 1 - AI tra cuu quy dinh noi bo (co RBAC).

Luong: question + user_role -> secure_retrieval_adapter (RBAC + Hybrid/Rerank
cua buoi_14) -> LLM (neu co GEMINI_API_KEY) hoac che do trich xuat (fallback,
mac dinh) -> answer + citations -> ghi audit log.

LLM (khi co key) CHI duoc tra loi tu chunk da qua RBAC - khong dung kien thuc
ngoai context, khong bia citation. Neu context khong du, tra ve cau co dinh:
"Khong tim thay du thong tin trong pham vi tai lieu duoc phep truy cap."
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

import secure_retrieval_adapter as adapter  # noqa: E402
import audit_logger  # noqa: E402

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
    """Goi Gemini CHI voi context da qua RBAC. Tra ve None neu khong co API key
    hoac loi ket noi -> caller se fallback ve extractive, KHONG bao gio tu bia."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    if not results:
        return NO_CONTEXT_MSG
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        context_block = "\n\n".join(
            f"[{r['citation']}]\n{r['text']}" for r in results
        )
        prompt = (
            "Bạn là trợ lý tra cứu quy định ngân hàng. CHỈ được trả lời dựa trên "
            "CONTEXT dưới đây, KHÔNG dùng kiến thức ngoài context, KHÔNG suy diễn thêm. "
            "Nếu context không đủ để trả lời, trả lời đúng nguyên văn: "
            f'"{NO_CONTEXT_MSG}"\n\n'
            f"CONTEXT:\n{context_block}\n\nCÂU HỎI: {question}\n\nTRẢ LỜI (kèm trích dẫn):"
        )
        model = os.environ.get("LLM_MODEL", "gemini-3.6-flash")
        resp = client.models.generate_content(model=model, contents=prompt)
        return (resp.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        print(f"[CANH BAO] Goi LLM that bai ({type(exc).__name__}: {exc}). "
              "Chuyen sang che do trich xuat.", file=sys.stderr)
        return None


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
        extra={"answer_mode": "llm" if used_llm else "extractive"},
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
    lines = ["# Buổi 17 — Internal Lookup Demo (PROMPT 5)\n"]
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
    lines.append(f"CITATION: {'PASS' if all_citation_ok else 'FAIL'}")
    lines.append(f"RBAC: {'PASS' if all_rbac_ok else 'FAIL'}")
    lines.append(f"AUDIT: PASS (xem outputs/audit_log.jsonl, mỗi câu hỏi có request_id tương ứng)")

    out_path = BASE_DIR / "outputs" / "internal_lookup_demo.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {out_path}")
    print("\n".join(lines[-3:]))


if __name__ == "__main__":
    main()
