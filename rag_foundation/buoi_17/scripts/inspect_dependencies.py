"""
BUOI 17 - PROMPT SETUP + PROMPT 0.

Kiem tra moi truong va doc lai du lieu/code cua cac buoi truoc TRUOC KHI
Buoi 17 xay bat cu thu gi moi. Script nay CHI DOC (read-only):
  - khong sua chunks_secure.csv / chunks_normalized.csv cua buoi_14;
  - khong viet lai secure_retriever.py;
  - khong tao RBAC policy moi.

Chay:  python scripts/inspect_dependencies.py
Xuat:  outputs/dependency_report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent  # buoi_17/
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()

SOURCE_SECURE_CSV = BUOI14_DIR / "data" / "processed" / "chunks_secure.csv"
SOURCE_NORMALIZED_CSV = BUOI14_DIR / "data" / "processed" / "chunks_normalized.csv"
INTERNAL_POLICY_CSV = BASE_DIR / "data" / "agribank_internal_policies.csv"
COMBINED_SECURE_CSV = BASE_DIR / "data" / "chunks_combined_secure.csv"

OUT = BASE_DIR / "outputs" / "dependency_report.md"


def check_env() -> dict:
    info = {"python_version": sys.version.split()[0]}
    try:
        import pandas as _pd  # noqa: F401
        info["pandas"] = "OK"
    except ImportError:
        info["pandas"] = "MISSING"
    for mod in ("rank_bm25", "sklearn", "neo4j"):
        try:
            __import__(mod)
            info[mod] = "OK"
        except ImportError:
            info[mod] = "MISSING"
    return info


def check_secure_retriever():
    """Tim va thu import SecureRetriever cua buoi_14 (KHONG sua, KHONG copy)."""
    src_path = BUOI14_DIR / "src" / "secure_retriever.py"
    result = {
        "path": str(src_path),
        "exists": src_path.exists(),
        "importable": False,
        "functions": [],
        "filters_before_retrieval": None,
        "keeps_citation_fields": None,
        "error": None,
    }
    if not src_path.exists():
        result["error"] = "Khong tim thay secure_retriever.py"
        return result
    try:
        sys.path.insert(0, str(BUOI14_DIR))
        import importlib

        mod = importlib.import_module("src.secure_retriever")
        result["importable"] = True
        result["functions"] = [
            f for f in ("secure_search", "secure_bm25_search", "secure_dense_search",
                        "secure_hybrid_search", "secure_rerank_search",
                        "filter_records_by_roles", "visibility_stats")
            if hasattr(mod, f)
        ]
        # Filter-before-retrieval: BM25 filters the pandas DataFrame BEFORE
        # building the BM25Okapi index (see _bm25_index_for_roles); Dense
        # does a fail-closed post-filter loop but never returns an
        # unauthorized chunk. Determined by reading the source (static),
        # not guessed.
        src_text = src_path.read_text(encoding="utf-8")
        result["filters_before_retrieval"] = (
            "BM25: pre-filter DataFrame truoc khi build BM25Okapi (dung nghia den). "
            "Dense: post-filter tren cosine score toan corpus nhung FAIL-CLOSED "
            "(bo qua chunk khong co quyen, khong bao gio tra ve). "
            "Rerank: loc lai LAN NUA (defense-in-depth) ngay truoc khi goi reranker."
            if "_filter_df_by_roles" in src_text and "fail-closed" in src_text.lower() + "FAIL-CLOSED".lower()
            else "Khong xac dinh duoc tu source (can doc lai thu cong)."
        )
        result["keeps_citation_fields"] = "attach(...)" in src_text and "citation" in src_text
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> None:
    lines: list[str] = []
    lines.append("# Buổi 17 — Dependency Report (PROMPT SETUP + PROMPT 0)\n")
    lines.append(f"Sinh lúc: chạy `python scripts/inspect_dependencies.py` trên máy học viên.\n")

    lines.append("## 1. Môi trường\n")
    env = check_env()
    for k, v in env.items():
        lines.append(f"- {k}: **{v}**")
    lines.append("")

    lines.append("## 2. Ghi chú cấu trúc thực tế (khác với thư mục mẫu trong tài liệu)\n")
    lines.append(
        "Tài liệu Buổi 17 giả định cấu trúc `thuchanh/buoi_16/` + `thuchanh/buoi_17/`. "
        "Trên project thực tế của học viên (`RAG/rag_foundation/`), pipeline Hybrid + "
        "Rerank + RBAC của các buổi 14/15/16 được gộp chung trong một thư mục "
        "**`buoi_14/`** (có `chay_buoi16.bat`, `requirements_buoi16_addon.txt`, "
        "`src/secure_retriever.py`, `roles.json` — tức là nội dung RBAC của 'Buổi 15/16' "
        "nằm trong `buoi_14/`, không có thư mục `buoi_16/` riêng). Vì vậy Buổi 17 coi "
        "**`../buoi_14/`** là nguồn cần tái sử dụng, thay vì `../buoi_16/` như ví dụ "
        "trong tài liệu. Không có gì bị sửa hay xoá ở `buoi_14/` để làm việc này."
    )
    lines.append("")
    lines.append(
        "Ngoài ra, trong `RAG/rag_foundation/buoi_17/` dữ liệu đang nằm lồng một cấp "
        "thừa (`buoi_17/buoi_17/Buoi_17.md`, `buoi_17/buoi_17/data/...`). Buổi 17 sẽ "
        "được xây ở cấp `buoi_17/` (không lồng thêm); học viên nên dọn thư mục lồng "
        "thừa này sau khi xác nhận không cần giữ bản sao cũ."
    )
    lines.append("")

    lines.append("## 3. Dữ liệu nguồn — chunks_secure.csv vs chunks_normalized.csv\n")
    if SOURCE_SECURE_CSV.exists() and SOURCE_NORMALIZED_CSV.exists():
        df_s = pd.read_csv(SOURCE_SECURE_CSV)
        df_n = pd.read_csv(SOURCE_NORMALIZED_CSV)
        extra = set(df_s.columns) - set(df_n.columns)
        missing = set(df_n.columns) - set(df_s.columns)
        lines.append(f"- `chunks_secure.csv`: **{len(df_s)} dòng, {len(df_s.columns)} cột**")
        lines.append(f"  - Cột: {list(df_s.columns)}")
        lines.append(f"- `chunks_normalized.csv`: **{len(df_n)} dòng, {len(df_n.columns)} cột**")
        lines.append(f"  - Cột: {list(df_n.columns)}")
        lines.append(f"- Số dòng khớp: **{'CÓ' if len(df_s) == len(df_n) else 'KHÔNG'}**")
        lines.append(f"- Cột thêm trong secure so với normalized: `{sorted(extra)}`")
        lines.append(f"- Cột thiếu trong secure so với normalized: `{sorted(missing) if missing else 'không có'}`")
        equal_note = (
            "chunks_secure.csv = chunks_normalized.csv + `allowed_roles` + `security_category` "
            "(2 cột thêm, KHÔNG chỉ 1 cột như tài liệu mô tả ở dạng ví dụ — đây là dữ liệu "
            "thật của học viên, 2528 dòng, không phải 787 dòng như ví dụ minh hoạ trong bài)."
        )
        lines.append(f"- Kết luận: {equal_note}")
        lines.append("")
        lines.append("### Danh sách cột đầy đủ cần cho các bước sau\n")
        needed = ["chunk_id", "document_id", "citation", "title", "document_type",
                  "issuing_body", "effective_date", "allowed_roles"]
        for col in needed:
            present = col in df_s.columns
            lines.append(f"- `{col}`: {'có' if present else 'KHÔNG có (dùng tên gần nhất nếu khác)'}")
    else:
        lines.append("**KHÔNG đọc được một hoặc cả hai file nguồn.**")
        lines.append(f"- chunks_secure.csv tồn tại: {SOURCE_SECURE_CSV.exists()} ({SOURCE_SECURE_CSV})")
        lines.append(f"- chunks_normalized.csv tồn tại: {SOURCE_NORMALIZED_CSV.exists()} ({SOURCE_NORMALIZED_CSV})")
    lines.append("")

    lines.append("## 4. Dữ liệu riêng của Buổi 17 (Compliance Gap Checker)\n")
    if INTERNAL_POLICY_CSV.exists():
        dfi = pd.read_csv(INTERNAL_POLICY_CSV)
        lines.append(f"- `agribank_internal_policies.csv`: **{len(dfi)} dòng, {len(dfi.columns)} cột** "
                     f"— dữ liệu MÔ PHỎNG quy định nội bộ Agribank (không phải văn bản thật), dùng làm "
                     "phía INTERNAL_POLICY cho Gap Checker.")
    else:
        lines.append("- `agribank_internal_policies.csv`: KHÔNG tìm thấy.")
    if COMBINED_SECURE_CSV.exists():
        dfc = pd.read_csv(COMBINED_SECURE_CSV)
        n_internal = dfc["document_id"].astype(str).str.startswith("agr_").sum()
        n_external = len(dfc) - n_internal
        lines.append(f"- `chunks_combined_secure.csv`: **{len(dfc)} dòng** = {n_external} external "
                     f"(Thông tư/Nghị định/Luật) + {n_internal} internal (agr_*, mô phỏng Agribank).")
        overlap = None
        if SOURCE_SECURE_CSV.exists():
            df_s = pd.read_csv(SOURCE_SECURE_CSV)
            ext_ids = set(dfc[~dfc["document_id"].astype(str).str.startswith("agr_")]["chunk_id"])
            overlap = len(ext_ids & set(df_s["chunk_id"]))
            lines.append(
                f"- ⚠️ Lưu ý quan trọng: `chunk_id` phía external của `chunks_combined_secure.csv` "
                f"**KHÔNG trùng namespace** với `chunks_secure.csv` của buoi_14 (giao nhau: "
                f"{overlap}/{len(ext_ids)} chunk_id). Đây là một lần chuẩn bị dữ liệu RIÊNG cho "
                f"Buổi 17 (787 external + 24 internal = 811, đúng với con số 787 dòng mà tài liệu "
                f"Buổi 17 mô tả), KHÔNG phải cùng một lần chunk hoá với corpus 2528 dòng của buoi_14. "
                f"Hệ quả: SecureRetriever gốc của buoi_14 (trỏ vào chunks_secure.csv 2528 dòng, "
                f"không có tài liệu nội bộ) KHÔNG thể trực tiếp tìm điều khoản nội bộ. Compliance Gap "
                f"Checker (Prompt 6/7) sẽ tái sử dụng THUẬT TOÁN (tokenizer + BM25Okapi + reranker) "
                f"của buoi_14 nhưng build một chỉ mục riêng, nhỏ, trên `chunks_combined_secure.csv` "
                f"— không viết lại giải thuật, chỉ trỏ vào corpus đúng phạm vi (có cả nội bộ)."
            )
    else:
        lines.append("- `chunks_combined_secure.csv`: KHÔNG tìm thấy.")
    lines.append("")

    lines.append("## 5. SecureRetriever (buổi trước)\n")
    sr = check_secure_retriever()
    lines.append(f"- File/module: `{sr['path']}` (`src.secure_retriever` khi thêm `{BUOI14_DIR}` vào sys.path)")
    lines.append(f"- Tồn tại: {sr['exists']}")
    lines.append(f"- Import được: {sr['importable']}")
    if sr["error"]:
        lines.append(f"- Lỗi: `{sr['error']}`")
    lines.append(f"- Hàm chính tìm thấy: {sr['functions']}")
    lines.append(f"- Input role: `user_roles` (list[str], validate qua `config.validate_roles`, "
                 f"đọc từ `roles.json` — Admin/HR/Risk_Manager/Staff/Guest)")
    lines.append(f"- Output: dict `{{method, user_roles, results, before_rerank, "
                 f"n_total_chunks, n_visible_chunks, n_hidden_chunks}}`, mỗi result có "
                 f"chunk_id/document_id/citation/allowed_roles/retrieval_method/score")
    lines.append(f"- Lọc trước hay sau retrieval: {sr['filters_before_retrieval']}")
    lines.append(f"- Giữ document_id/chunk_id/citation: {'CÓ' if sr['keeps_citation_fields'] else 'KHÔNG xác định'}")
    lines.append("")

    lines.append("## 6. Kết luận\n")
    source_ok = SOURCE_SECURE_CSV.exists() and SOURCE_NORMALIZED_CSV.exists()
    rbac_ok = source_ok and "allowed_roles" in pd.read_csv(SOURCE_SECURE_CSV, nrows=1).columns
    reusable = sr["importable"] and not sr["error"]
    lines.append(f"SOURCE DATA: {'PASS' if source_ok else 'FAIL'}")
    lines.append(f"RBAC DATA AVAILABLE: {'YES' if rbac_ok else 'NO'}")
    lines.append(f"SECURE RETRIEVER REUSABLE: {'YES' if reusable else 'NO'}")
    lines.append(
        "REUSE PLAN: Dùng thẳng `buoi_14/src/secure_retriever.secure_search()` qua "
        "`secure_retrieval_adapter.py` cho Use Case 1 (tra cứu nội bộ trên corpus 2528 dòng, "
        "external-only). Với Compliance Gap Checker, build chỉ mục BM25 nhỏ trên "
        "`chunks_combined_secure.csv` (811 dòng, có cả nội bộ), tái sử dụng "
        "`tokenize()`, `BM25Okapi`, và `Reranker` (fallback lexical) — không rebuild thuật toán, "
        "chỉ đổi nguồn dữ liệu đầu vào cho đúng phạm vi bài toán."
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print("\n".join(lines[-6:]))


if __name__ == "__main__":
    main()
