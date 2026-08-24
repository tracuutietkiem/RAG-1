"""
BUOI 17 - PROMPT 2: chung minh Secure Retrieval reuse dung.

4 test bat buoc:
  1. role duoc phep nhan duoc chunk;
  2. role khong duoc phep KHONG nhan chunk do;
  3. unauthorized chunk khong xuat hien trong context (kiem tra tren TOAN BO
     candidate truoc rerank, khong chi ket qua cuoi);
  4. citation/document_id/chunk_id khong bi mat.

Xuat: outputs/secure_retrieval_test.md
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
import secure_retrieval_adapter as adapter  # noqa: E402

OUT = BASE_DIR / "outputs" / "secure_retrieval_test.md"


def main() -> None:
    lines = ["# Buổi 17 — Secure Retrieval Test (PROMPT 2)\n"]
    all_pass = True

    # --- Tim mot chunk chi HR/Admin xem duoc (khong co Staff/Guest/Risk_Manager) de test that -----
    import importlib
    sr = importlib.import_module("src.secure_retriever")
    records = sr.load_secure_records()
    hr_only = [r for r in records if set(r["allowed_roles"]) == {"Admin", "HR"}]
    lines.append(f"Số chunk chỉ dành riêng cho {{Admin, HR}} (không Staff/Guest/Risk_Manager): {len(hr_only)}")
    if not hr_only:
        lines.append("**Không tìm thấy chunk hạn chế tuyệt đối — dùng câu hỏi chủ đề HR để test theo tỉ lệ hiển thị thay vì theo 1 chunk_id cụ thể.**")
    lines.append("")

    # --- Test 1 & 2: role duoc phep vs khong duoc phep, cung 1 cau hoi chu de HR ------------------
    question_hr = "Quy định về bổ nhiệm, miễn nhiệm cán bộ quản lý là gì?"
    out_hr = adapter.secure_search(question_hr, ["HR"], method="hybrid_rerank", top_k=5)
    out_guest = adapter.secure_search(question_hr, ["Guest"], method="hybrid_rerank", top_k=5)

    hr_chunk_ids = {r["chunk_id"] for r in out_hr["results"]}
    guest_chunk_ids = {r["chunk_id"] for r in out_guest["results"]}

    test1_pass = len(out_hr["results"]) > 0
    lines.append(f"## Test 1 — role được phép (HR) nhận được chunk\n")
    lines.append(f"- Câu hỏi: *{question_hr}*")
    lines.append(f"- Số chunk HR nhận được: {len(out_hr['results'])}")
    lines.append(f"- Kết quả: **{'PASS' if test1_pass else 'FAIL'}**\n")

    lines.append(f"## Test 2 — role không được phép (Guest) không nhận đúng các chunk hạn chế đó\n")
    # kiem tra: moi chunk HR nhan duoc ma Guest KHONG co trong allowed_roles thi Guest khong duoc tra ve
    leaked = []
    for r in out_hr["results"]:
        if "Guest" not in r["allowed_roles"] and r["chunk_id"] in guest_chunk_ids:
            leaked.append(r["chunk_id"])
    test2_pass = len(leaked) == 0
    lines.append(f"- Chunk HR-only vô tình lọt vào kết quả của Guest: {leaked or '(không có)'}")
    lines.append(f"- Kết quả: **{'PASS' if test2_pass else 'FAIL'}**\n")

    # --- Test 3: unauthorized chunk khong vao context, kiem tra ca before_rerank ------------------
    raw = importlib.import_module("src.secure_retriever").secure_search(
        question_hr, ["Guest"], method="hybrid_rerank", top_k=5
    )
    all_candidates = raw.get("before_rerank", []) + raw.get("results", [])
    unauthorized_in_context = [
        c["chunk_id"] for c in all_candidates
        if "Guest" not in (c.get("allowed_roles") or [])
    ]
    test3_pass = len(unauthorized_in_context) == 0
    lines.append(f"## Test 3 — unauthorized chunk không xuất hiện trong context (kể cả before_rerank)\n")
    lines.append(f"- Số candidate kiểm tra (before_rerank + results): {len(all_candidates)}")
    lines.append(f"- Candidate không đúng quyền Guest lọt vào: {unauthorized_in_context or '(không có)'}")
    lines.append(f"- Kết quả: **{'PASS' if test3_pass else 'FAIL'}**\n")

    # --- Test 4: citation/document_id/chunk_id khong mat ------------------------------------------
    missing_fields = []
    for r in out_hr["results"]:
        for field in ("chunk_id", "document_id", "citation"):
            if not r.get(field):
                missing_fields.append((r.get("chunk_id", "?"), field))
    test4_pass = len(missing_fields) == 0
    lines.append(f"## Test 4 — citation/document_id/chunk_id không bị mất\n")
    lines.append(f"- Trường bị thiếu: {missing_fields or '(không có)'}")
    lines.append(f"- Ví dụ 1 kết quả đầy đủ: `{out_hr['results'][0] if out_hr['results'] else 'N/A'}`")
    lines.append(f"- Kết quả: **{'PASS' if test4_pass else 'FAIL'}**\n")

    all_pass = test1_pass and test2_pass and test3_pass and test4_pass

    lines.append("## Kết luận\n")
    lines.append(f"SECURE RETRIEVAL REUSE: {'PASS' if all_pass else 'FAIL'}")
    lines.append(f"NO UNAUTHORIZED CONTEXT: {'PASS' if test3_pass else 'FAIL'}")
    lines.append(f"CITATION PRESERVED: {'PASS' if test4_pass else 'FAIL'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
