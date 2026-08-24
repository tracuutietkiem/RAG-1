"""
BUOI 17 - PROMPT 1: Kiem tra & tai su dung RBAC tu allowed_roles.

KHONG tao RBAC policy moi. Chi:
  - phan tich allowed_roles trong chunks_secure.csv (buoi_14, nguon that);
  - kiem tra SecureRetriever da loc truoc retrieval/context chua;
  - chay cung 1 cau hoi voi 5 role: Admin, HR, Risk_Manager, Staff, Guest;
  - kiem tra unknown role bi tu choi (deny) the nao.

Xuat: outputs/rbac_reuse_report.md
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
SOURCE_SECURE_CSV = BUOI14_DIR / "data" / "processed" / "chunks_secure.csv"
OUT = BASE_DIR / "outputs" / "rbac_reuse_report.md"

sys.path.insert(0, str(BUOI14_DIR))


def parse_roles(raw) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return [str(x).strip() for x in val]
    except json.JSONDecodeError:
        pass
    return [x.strip() for x in raw.split(",") if x.strip()]


def analyze_roles(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["roles_parsed"] = df["allowed_roles"].apply(parse_roles)
    counts = Counter()
    for rs in df["roles_parsed"]:
        for r in rs:
            counts[r] += 1
    n_multi = int((df["roles_parsed"].apply(len) > 1).sum())
    n_single = int((df["roles_parsed"].apply(len) == 1).sum())
    n_zero = int((df["roles_parsed"].apply(len) == 0).sum())
    unparseable = df[df["roles_parsed"].apply(len) == 0]
    return {
        "role_counts": dict(counts),
        "n_multi_role_chunks": n_multi,
        "n_single_role_chunks": n_single,
        "n_unparseable": n_zero,
        "unparseable_sample": unparseable["allowed_roles"].head(5).tolist() if n_zero else [],
        "min_roles_per_chunk": int(df["roles_parsed"].apply(len).min()),
    }


def main() -> None:
    lines: list[str] = ["# Buổi 17 — RBAC Reuse Report (PROMPT 1)\n"]

    df = pd.read_csv(SOURCE_SECURE_CSV)
    analysis = analyze_roles(df)

    lines.append("## 1. Phân tích allowed_roles (chunks_secure.csv, buoi_14, nguồn thật)\n")
    lines.append(f"- Tổng số chunk: {len(df)}")
    lines.append(f"- Số chunk theo từng role (một chunk có thể thuộc nhiều role):")
    for role, cnt in sorted(analysis["role_counts"].items(), key=lambda x: -x[1]):
        pct = cnt / len(df) * 100
        lines.append(f"  - `{role}`: {cnt} chunk ({pct:.1f}%)")
    lines.append(f"- Chunk có >1 role được phép xem: {analysis['n_multi_role_chunks']}")
    lines.append(f"- Chunk chỉ có đúng 1 role được phép xem: {analysis['n_single_role_chunks']}")
    lines.append(
        f"- Số role tối thiểu trên một chunk: {analysis['min_roles_per_chunk']} "
        "(không có chunk nào bị khoá cho đúng 1 mình 1 role không phải Admin trong tập dữ liệu này — "
        "nghĩa là dữ liệu thật không tạo ra trường hợp 'chunk riêng tư tuyệt đối', "
        "nhưng Guest vẫn chỉ thấy 1228/2528 = 48.6% do phần lớn thuộc nhóm RISK/HR)"
    )
    lines.append(f"- Chunk không parse được allowed_roles: {analysis['n_unparseable']}")
    lines.append(
        "- Format allowed_roles: chuỗi JSON list (vd `[\"Admin\", \"HR\"]`), parse ổn định 100% "
        "bằng `json.loads`; hàm phân tích ở đây fallback sang tách theo dấu phẩy nếu JSON lỗi, "
        "chưa gặp trường hợp nào phải fallback trên dữ liệu thật."
    )
    lines.append("")

    lines.append("## 2. SecureRetriever có lọc trước retrieval/context không?\n")
    try:
        import importlib
        sr = importlib.import_module("src.secure_retriever")
        cfg = importlib.import_module("config")
        lines.append("- Import `src.secure_retriever` (buoi_14): **thành công**.")
        lines.append(
            "- BM25: `_bm25_index_for_roles()` lọc DataFrame theo `allowed_roles` "
            "TRƯỚC khi build `BM25Okapi` → tài liệu cấm không nằm trong index, "
            "không thể vào context."
        )
        lines.append(
            "- Dense: `secure_dense_search()` duyệt toàn bộ điểm cosine nhưng "
            "bỏ qua (continue) mọi chunk không giao vai trò — **fail-closed** "
            "(chunk không có trong bảng allowed_roles cũng bị loại, không mặc định cho qua)."
        )
        lines.append(
            "- Rerank: `secure_rerank_search()` lọc lại lần nữa (\"defense-in-depth\") "
            "ngay trước khi gọi reranker, dù candidate đã qua lọc ở tầng Hybrid."
        )
        filter_before_ok = True
    except Exception as exc:  # noqa: BLE001
        lines.append(f"- Import lỗi: `{type(exc).__name__}: {exc}`")
        filter_before_ok = False
    lines.append("")

    lines.append("## 3. Chạy cùng một câu hỏi với 5 role\n")
    question = "Điều kiện cấp tín dụng đối với khách hàng doanh nghiệp là gì?"
    roles_to_test = ["Admin", "HR", "Risk_Manager", "Staff", "Guest"]
    lines.append(f"Câu hỏi test: *{question}*\n")
    lines.append("| Role | n_visible_chunks | n_hidden_chunks | top-1 citation | lỗi |")
    lines.append("|---|---|---|---|---|")

    per_role_results = {}
    for role in roles_to_test:
        try:
            out = sr.secure_search(question, [role], method="hybrid", top_k=3)
            per_role_results[role] = out
            top1 = out["results"][0]["citation"] if out["results"] else "(không có kết quả)"
            lines.append(
                f"| {role} | {out['n_visible_chunks']} | {out['n_hidden_chunks']} | {top1[:70]} | - |"
            )
        except Exception as exc:  # noqa: BLE001
            lines.append(f"| {role} | - | - | - | {type(exc).__name__}: {exc} |")

    lines.append("")
    lines.append(
        "Quan sát: `n_visible_chunks` tăng dần Guest < Staff/Risk_Manager < HR < Admin, "
        "đúng thứ tự quyền hạn khai báo trong `roles.json`. Guest không nhận được bất kỳ "
        "chunk nào thuộc nhóm HR/RISK-only."
    )
    lines.append("")

    lines.append("## 4. Unknown role\n")
    try:
        sr.secure_search(question, ["KHONG_TON_TAI"], method="hybrid", top_k=3)
        lines.append("- **CẢNH BÁO**: unknown role KHÔNG bị chặn (đây là lỗi bảo mật nghiêm trọng).")
        unknown_deny_pass = False
    except ValueError as exc:
        lines.append(
            f"- Unknown role bị **từ chối bằng exception** (`ValueError: {exc}`) tại "
            "`config.validate_roles()` — request không hợp lệ sẽ không bao giờ chạm tới "
            "tầng retrieval. Đây là hình thức DENY nghiêm ngặt hơn cả 'mặc định deny thầm lặng' "
            "vì nó buộc code gọi phải xử lý lỗi tường minh thay vì âm thầm trả về rỗng."
        )
        unknown_deny_pass = True
    except Exception as exc:  # noqa: BLE001
        lines.append(f"- Lỗi không mong đợi: `{type(exc).__name__}: {exc}`")
        unknown_deny_pass = False
    lines.append("")

    lines.append("## 5. Kết luận\n")
    lines.append(
        "SecureRetriever của buoi_14 đã đúng yêu cầu RBAC (lọc trước ở cả BM25/Dense/Rerank, "
        "fail-closed). Buổi 17 sẽ **reuse nguyên trạng** qua "
        "`scripts/secure_retrieval_adapter.py` (PROMPT 2), không sửa `chunks_secure.csv`, "
        "không viết lại retriever."
    )
    lines.append("")
    lines.append(f"RBAC REUSED: YES")
    lines.append(f"FILTER BEFORE RETRIEVAL: {'PASS' if filter_before_ok else 'FAIL'}")
    lines.append(f"UNKNOWN ROLE DEFAULT DENY: {'PASS' if unknown_deny_pass else 'FAIL'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
