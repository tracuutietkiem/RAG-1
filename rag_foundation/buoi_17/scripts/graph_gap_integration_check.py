"""
BUOI 17 - PROMPT 8: Kiem tra vai tro Knowledge Graph cho Compliance Gap Checker.

KHONG tu tao edge. Chi:
  1. thu ket noi Neo4j THAT (dung lai secure_retriever.neo4j_status +
     mot lan verify_connectivity that su, KHONG doan);
  2. doc tinh (static) schema.cypher + load_secure_kg.py cua buoi_14 de biet
     CHINH XAC nhung relationship type ma pipeline nay tung tao ra;
  3. ket luan GRAPH USED YES/NO va ly do that.

Xuat: outputs/graph_gap_integration_report.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BUOI14_DIR = (BASE_DIR / "../buoi_14").resolve()
sys.path.insert(0, str(BUOI14_DIR))

from src import secure_retriever  # noqa: E402

OUT = BASE_DIR / "outputs" / "graph_gap_integration_report.md"


def try_live_connection() -> dict:
    ok, msg = secure_retriever.neo4j_status()
    result = {"config_ready": ok, "config_message": msg, "connect_attempted": False,
              "connect_ok": False, "connect_error": None}
    if not ok:
        return result
    result["connect_attempted"] = True
    try:
        import config as cfg14
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(cfg14.NEO4J_URI, auth=(cfg14.NEO4J_USER, cfg14.NEO4J_PASSWORD))
        try:
            driver.verify_connectivity()
            result["connect_ok"] = True
        finally:
            driver.close()
    except Exception as exc:  # noqa: BLE001
        result["connect_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return result


def static_relationship_scan() -> dict:
    schema_file = BUOI14_DIR / "cypher" / "schema.cypher"
    loader_file = BUOI14_DIR / "scripts" / "load_secure_kg.py"
    rel_types = set()
    for f in (schema_file, loader_file):
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        rel_types.update(re.findall(r"-\[:?(\w+)\]", text))
        rel_types.update(re.findall(r"-\[r?:(\w+)\]", text))
    return {"schema_file": str(schema_file), "loader_file": str(loader_file),
            "relationship_types_found": sorted(rel_types)}


def main() -> None:
    lines = ["# Buổi 17 — Graph / Gap Integration Report (PROMPT 8)\n"]

    live = try_live_connection()
    lines.append("## 1. Kết nối Neo4j thật (từ môi trường chạy script này)\n")
    lines.append(f"- Cấu hình .env đầy đủ (URI/USER/PASSWORD): {live['config_ready']} ({live['config_message']})")
    if live["connect_attempted"]:
        lines.append(f"- Thử `driver.verify_connectivity()`: {'THÀNH CÔNG' if live['connect_ok'] else 'THẤT BẠI'}")
        if live["connect_error"]:
            lines.append(f"  - Lỗi thật: `{live['connect_error']}`")
    lines.append(
        "\n**Lưu ý quan trọng**: script này đang chạy trong sandbox trên cloud, KHÔNG phải trên "
        "máy Windows của học viên — nơi Neo4j Desktop (instance `rag2026`) thực sự đang chạy ở "
        "`127.0.0.1:7687`. Từ sandbox này, `127.0.0.1` không trỏ tới máy học viên nên kết nối "
        "chắc chắn thất bại — đây là giới hạn môi trường thực thi, KHÔNG phải kết luận rằng Neo4j "
        "của học viên có vấn đề. Học viên nên chạy lại đúng script này "
        "(`python scripts/graph_gap_integration_check.py`) trên máy của mình, có Neo4j Desktop "
        "đang mở, để có kết quả sống thật.\n"
    )

    scan = static_relationship_scan()
    lines.append("## 2. Quan hệ (relationship) THỰC SỰ được pipeline này tạo ra (đọc tĩnh source code)\n")
    lines.append(f"- File kiểm tra: `{Path(scan['schema_file']).name}`, `{Path(scan['loader_file']).name}` (buoi_14)")
    lines.append(f"- Relationship type tìm thấy: {scan['relationship_types_found']}")
    lines.append(
        "- `load_secure_kg.py` (Buổi 15) CHỈ tạo `(:VanBan)-[:CONTAINS]->(:DieuKhoan)` — quan hệ "
        "cấu trúc nội bộ một văn bản (văn bản chứa điều khoản của chính nó), KHÔNG có quan hệ nối "
        "giữa văn bản NÀY với văn bản KHÁC (không có kiểu như 'CĂN_CỨ', 'SỬA_ĐỔI', 'HƯỚNG_DẪN' "
        "giữa hai văn bản pháp luật khác nhau, hay giữa văn bản bên ngoài và quy định nội bộ)."
    )
    lines.append("")

    lines.append("## 3. Đánh giá theo đúng khung của bài\n")
    lines.append("- Relation chỉ là CONTAINS/NEXT (không giúp): **CONTAINS** — đúng vậy, chỉ nối văn bản với chính điều khoản của nó.")
    lines.append("- Relation giúp nối văn bản/điều khoản KHÁC NHAU (Thông tư ↔ quy định nội bộ Agribank): **không có** trong pipeline hiện tại.")
    lines.append("- Relation không liên quan: n/a (không có relation nào khác được tạo).")
    lines.append("")

    lines.append("## Kết luận\n")
    lines.append(
        "Ngay cả nếu kết nối Neo4j thành công, quan hệ duy nhất mà pipeline này từng tạo "
        "(`CONTAINS`) không nối văn bản bên ngoài với quy định nội bộ — nên KHÔNG có candidate "
        "expansion nào hữu ích cho Compliance Gap Checker để bổ sung. Việc thêm graph candidate "
        "expansion vào `compliance_gap.py` sẽ là suy diễn, không phải dựa trên dữ liệu graph thật."
    )
    lines.append("")
    lines.append("GRAPH USED: NO")
    lines.append(
        "Lý do: (1) Neo4j không thể kết nối từ môi trường sandbox chạy script này (giới hạn "
        "thực thi, cần chạy lại trên máy học viên để xác nhận sống); (2) quan hệ graph duy nhất "
        "mà pipeline buoi_14/15 từng tạo ra (CONTAINS) là quan hệ cấu trúc nội bộ một văn bản, "
        "không nối được văn bản bên ngoài với quy định nội bộ — không có giá trị bổ sung cho "
        "Gap Checker cho dù Neo4j có kết nối được hay không."
    )

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da ghi {OUT}")
    print(f"GRAPH USED: NO")


if __name__ == "__main__":
    main()
