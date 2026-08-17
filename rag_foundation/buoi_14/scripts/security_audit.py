#!/usr/bin/env python3
"""
BUOI 15 - PROMPT 5: Kiem thu ro ri du lieu tu dong (Security Integration Test).

    python scripts/security_audit.py

Ghi: buoi_14/outputs/security_audit_report.md

Thiet ke:
  - 5 test case, moi case gan voi MOT CHUNK cu the (khong phai ca van ban) vi
    mot van ban trong corpus nay co the vua chua Dieu nhay cam (HR/Risk) vua
    chua Dieu quy dinh chung (GENERAL) - kiem tra o muc document_id se sai
    (Guest van duoc phep thay cac Dieu GENERAL cua chinh van ban do).
  - unauthorized_roles: chay secure_search, ASSERT target_sensitive_chunk_id
    KHONG xuat hien trong Top-K (K = TOP_K_LEAK_CHECK) o CA 4 phuong phap
    (bm25, dense, hybrid, hybrid_rerank). Day la dieu kien PASS/FAIL bat buoc.
  - authorized_roles: chay secure_search, ghi nhan (thong tin, KHONG lam FAIL
    bai kiem thu bao mat) target co xuat hien trong Top-K rong hon hay khong -
    dung de bai cho phep "neu diem tuong dong du cao", tuc day la kiem tra
    CHAT LUONG retrieval chu khong phai kiem tra BAO MAT.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import secure_retriever as sr  # noqa: E402

TOP_K_LEAK_CHECK = 10
TOP_K_VISIBILITY_CHECK = 20
CANDIDATE_K = 30
METHODS = ("bm25", "dense", "hybrid", "hybrid_rerank")

TEST_CASES = [
    {
        "name": "HR-01 · Bổ nhiệm Trưởng kiểm toán nội bộ",
        "query": "Thẩm quyền bổ nhiệm, miễn nhiệm Trưởng kiểm toán nội bộ của tổ chức tín dụng",
        "target_sensitive_chunk_id": "27257_D14_023",
        "target_sensitive_document_id": "27257",
        "authorized_roles": ["HR"],
        "unauthorized_roles": ["Guest"],
    },
    {
        "name": "HR-02 · Miễn nhiệm Chủ tịch HĐQT",
        "query": "Miễn nhiệm, bãi nhiệm Chủ tịch Hội đồng quản trị tổ chức tín dụng",
        "target_sensitive_chunk_id": "166170_D46_062",
        "target_sensitive_document_id": "166170",
        "authorized_roles": ["Admin"],
        "unauthorized_roles": ["Staff"],
    },
    {
        "name": "HR-03 · Nhiệm kỳ Tổng giám đốc",
        "query": "Nhiệm kỳ và trách nhiệm của Tổng giám đốc ngân hàng chính sách",
        "target_sensitive_chunk_id": "166170_D22_027",
        "target_sensitive_document_id": "166170",
        "authorized_roles": ["HR"],
        "unauthorized_roles": ["Risk_Manager"],
    },
    {
        "name": "RISK-01 · Giới hạn cấp tín dụng",
        "query": "Giới hạn cấp tín dụng đối với một khách hàng và người có liên quan",
        "target_sensitive_chunk_id": "166170_D136K1_214",
        "target_sensitive_document_id": "166170",
        "authorized_roles": ["Risk_Manager"],
        "unauthorized_roles": ["Guest"],
    },
    {
        "name": "RISK-02 · Quản lý khoản cấp tín dụng có vấn đề",
        "query": "Quản lý khoản cấp tín dụng có vấn đề tại tổ chức tín dụng",
        "target_sensitive_chunk_id": "186888_D33_052",
        "target_sensitive_document_id": "186888",
        "authorized_roles": ["Staff"],
        "unauthorized_roles": ["HR"],
    },
]


def _log_error(exc: BaseException, context: str) -> Path:
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = config.OUTPUTS_DIR / f"error_security_audit_{ts}.txt"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().isoformat()}] Loi trong: {context}\n")
        fh.write(f"{type(exc).__name__}: {exc}\n\n")
        fh.write(traceback.format_exc())
    return log_path


def _chunk_ids_of(results: list[dict]) -> set[str]:
    return {r.get("chunk_id", "") for r in results}


def run_one_test_case(tc: dict) -> dict:
    target = tc["target_sensitive_chunk_id"]
    per_method: dict[str, dict] = {}
    leak_detected = False

    for method in METHODS:
        # ---- 1) unauthorized: BAT BUOC khong duoc thay target trong Top-K ----
        out_unauth = sr.secure_search(
            tc["query"], tc["unauthorized_roles"], method=method,
            top_k=TOP_K_LEAK_CHECK, candidate_k=CANDIDATE_K,
        )
        unauth_ids = _chunk_ids_of(out_unauth["results"])
        leaked = target in unauth_ids
        leak_detected = leak_detected or leaked

        # ---- 2) authorized: THONG TIN, khong lam fail bai test ----
        out_auth = sr.secure_search(
            tc["query"], tc["authorized_roles"], method=method,
            top_k=TOP_K_VISIBILITY_CHECK, candidate_k=CANDIDATE_K,
        )
        auth_ids = _chunk_ids_of(out_auth["results"])
        visible_for_authorized = target in auth_ids

        per_method[method] = {
            "leaked": leaked,
            "unauthorized_top_k_ids": sorted(unauth_ids),
            "visible_for_authorized": visible_for_authorized,
            "authorized_top_k_rank": (
                next((r["rank"] for r in out_auth["results"] if r["chunk_id"] == target), None)
            ),
        }

    return {
        "name": tc["name"],
        "query": tc["query"],
        "target_sensitive_chunk_id": target,
        "target_sensitive_document_id": tc["target_sensitive_document_id"],
        "authorized_roles": tc["authorized_roles"],
        "unauthorized_roles": tc["unauthorized_roles"],
        "status": "FAIL" if leak_detected else "PASS",
        "per_method": per_method,
    }


def write_report(case_results: list[dict]) -> Path:
    n_total = len(case_results)
    n_pass = sum(1 for c in case_results if c["status"] == "PASS")
    n_fail = n_total - n_pass
    n_checks = n_total * len(METHODS)

    L: list[str] = []
    add = L.append
    add("# Báo cáo Kiểm định Bảo mật (Security Audit) — Buổi 15\n")
    add(f"- Thời điểm chạy: {datetime.now().isoformat(timespec='seconds')}")
    add(f"- Nguồn dữ liệu: `data/processed/chunks_secure.csv`")
    add(f"- Vai trò hệ thống: `{config.ALL_ROLES}`")
    add(f"- Ngưỡng kiểm tra rò rỉ: Top-{TOP_K_LEAK_CHECK} "
        f"(candidate_k={CANDIDATE_K}), 4 phương pháp: `{', '.join(METHODS)}`\n")

    add("## 1. Tổng quan\n")
    add(f"- Tổng số test case: **{n_total}**")
    add(f"- Tổng số lượt kiểm tra rò rỉ (test case × phương pháp): **{n_checks}**")
    add(f"- PASS: **{n_pass}** / FAIL: **{n_fail}**\n")

    add("## 2. Kết quả từng test case\n")
    add("| # | Test case | Target chunk | Unauthorized roles | Authorized roles | Kết quả |")
    add("|---|---|---|---|---|---|")
    for i, c in enumerate(case_results, start=1):
        icon = "✅ PASS" if c["status"] == "PASS" else "🚨 FAIL"
        add(f"| {i} | {c['name']} | `{c['target_sensitive_chunk_id']}` | "
            f"`{c['unauthorized_roles']}` | `{c['authorized_roles']}` | {icon} |")
    add("")

    add("## 3. Bằng chứng kiểm thử chi tiết\n")
    for i, c in enumerate(case_results, start=1):
        add(f"### {i}. {c['name']} — {c['status']}\n")
        add(f"- Câu hỏi: *{c['query']}*")
        add(f"- Tài liệu nhạy cảm đích: `{c['target_sensitive_chunk_id']}` "
            f"(văn bản `{c['target_sensitive_document_id']}`)")
        add(f"- Vai trò KHÔNG được phép: `{c['unauthorized_roles']}`")
        add(f"- Vai trò ĐƯỢC phép: `{c['authorized_roles']}`\n")
        add("| Phương pháp | Rò rỉ với unauthorized_roles? | Xuất hiện với authorized_roles? | Rank (authorized) |")
        add("|---|---|---|---|")
        for method in METHODS:
            m = c["per_method"][method]
            leaked_txt = "🚨 CÓ — RÒ RỈ" if m["leaked"] else "Không (an toàn)"
            visible_txt = "Có" if m["visible_for_authorized"] else "Không (dưới ngưỡng liên quan)"
            rank_txt = m["authorized_top_k_rank"] if m["authorized_top_k_rank"] is not None else "—"
            add(f"| {method} | {leaked_txt} | {visible_txt} | {rank_txt} |")
        add("")
        if c["status"] == "PASS":
            add(f"> ✅ **Bằng chứng PASS:** với vai trò `{c['unauthorized_roles']}`, không có "
                f"phương pháp nào trong `{list(METHODS)}` trả về chunk `{c['target_sensitive_chunk_id']}` "
                f"trong Top-{TOP_K_LEAK_CHECK}.\n")
        else:
            leaking_methods = [m for m in METHODS if c["per_method"][m]["leaked"]]
            add(f"> 🚨 **CẢNH BÁO RÒ RỈ DỮ LIỆU:** vai trò `{c['unauthorized_roles']}` (không có quyền) "
                f"vẫn nhìn thấy chunk `{c['target_sensitive_chunk_id']}` qua phương pháp: "
                f"`{leaking_methods}`. Cần rà soát lại tầng lọc quyền (Access Filtering) của "
                f"`src/secure_retriever.py` cho (các) phương pháp này trước khi đưa vào sử dụng.\n")

    add("## 4. Kết luận\n")
    if n_fail == 0:
        add(f"✅ **Hệ thống ĐẠT chứng nhận an toàn dữ liệu mức cơ bản** — "
            f"toàn bộ {n_checks} lượt kiểm tra rò rỉ (5 test case × 4 phương pháp) đều PASS. "
            f"Không phát hiện trường hợp vai trò không đủ quyền nhìn thấy tài liệu nhạy cảm "
            f"của vai trò khác, ở cả 3 tầng: BM25 (pre-filter DataFrame), Dense (post-filter "
            f"metadata), và Hybrid + Reranker (candidate đã lọc quyền trước khi vào Reranker).")
    else:
        add(f"🚨 **Hệ thống CHƯA ĐẠT chứng nhận an toàn dữ liệu** — phát hiện **{n_fail}/{n_total}** "
            f"test case bị rò rỉ. Xem chi tiết bằng chứng ở mục 3, khắc phục tầng lọc quyền tương "
            f"ứng rồi chạy lại `python scripts/security_audit.py` trước khi đưa hệ thống vào sử dụng.")
    add("")
    add("> Lưu ý: test case này chỉ kiểm tra tầng BM25 / Dense / Hybrid / Reranker (dữ liệu CSV). "
        "Tầng Graph (Neo4j) được kiểm tra riêng qua `src.secure_retriever.secure_graph_hints()` — "
        "chạy `python scripts/secure_search_demo.py` với Neo4j đang hoạt động để quan sát trực tiếp.")

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    config.SECURITY_AUDIT_REPORT.write_text("\n".join(L), encoding="utf-8")
    return config.SECURITY_AUDIT_REPORT


def run() -> int:
    print("=" * 78)
    print("BUOI 15 - SECURITY AUDIT (kiem thu ro ri du lieu tu dong)")
    print("=" * 78)
    case_results = []
    for i, tc in enumerate(TEST_CASES, start=1):
        print(f"\n[{i}/{len(TEST_CASES)}] {tc['name']}")
        result = run_one_test_case(tc)
        case_results.append(result)
        icon = "PASS" if result["status"] == "PASS" else "FAIL <-- RO RI!"
        print(f"    -> {icon}")

    n_pass = sum(1 for c in case_results if c["status"] == "PASS")
    n_fail = len(case_results) - n_pass
    print("\n" + "=" * 78)
    print(f"TONG KET: {n_pass}/{len(case_results)} PASS, {n_fail} FAIL")
    print("=" * 78)

    path = write_report(case_results)
    print(f"\nDa ghi bao cao: {path.relative_to(config.BASE_DIR)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:  # noqa: BLE001
        log_path = _log_error(exc, context="scripts/security_audit.py")
        print(f"\n[LOI] {type(exc).__name__}: {exc}")
        print(f"[LOI] Da ghi log chi tiet vao: {log_path}")
        sys.exit(2)
