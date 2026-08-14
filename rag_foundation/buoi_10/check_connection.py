"""Kiểm tra kết nối Neo4j trước khi chạy `load` — chạy trong vài giây, không ghi gì.

Dùng để tách bạch lỗi kết nối (sai mật khẩu, chưa start instance, chưa tạo
database) ra khỏi lỗi pipeline. Nếu script này chạy được thì `load` sẽ không
fail vì lý do kết nối.

Chạy: python check_connection.py
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from src.neo4j_loader import Neo4jConfig, default_driver_factory


def main() -> int:
    load_dotenv()
    config = Neo4jConfig.from_env()

    print(f"URI      : {config.uri}")
    print(f"User     : {config.user}")
    print(f"Password : {'(đã điền)' if config.password else '(TRỐNG — kiểm tra .env)'}")
    print(f"Database : {config.database}")
    print("-" * 50)

    if not config.password:
        print("LỖI: NEO4J_PASSWORD trống. Mở file .env và điền mật khẩu.", file=sys.stderr)
        return 2

    try:
        driver = default_driver_factory(config)
    except Exception as exc:  # noqa: BLE001 - cần bắt rộng để báo lỗi thân thiện
        print(f"LỖI khi tạo driver: {exc}", file=sys.stderr)
        return 3

    try:
        with driver.session(database=config.database) as session:
            value = session.run("RETURN 1 AS ok").single()["ok"]
            if value != 1:
                print(f"LỖI: truy vấn thử trả về {value!r}, kỳ vọng 1", file=sys.stderr)
                return 4

            counts = session.run(
                "MATCH (n) RETURN labels(n) AS labels, count(*) AS n"
            ).data()
        print("KẾT NỐI THÀNH CÔNG.")
        if counts:
            print("Dữ liệu hiện có trong database:")
            for row in counts:
                print(f"  {row['labels']}: {row['n']}")
        else:
            print("Database đang rỗng — sẵn sàng để nạp.")
        return 0
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        print(f"LỖI khi kết nối/truy vấn: {message}", file=sys.stderr)

        lowered = message.lower()
        if "database does not exist" in lowered or "databasenotfound" in lowered:
            print(
                f"\n>>> Database '{config.database}' chưa tồn tại.\n"
                "    - Nếu dùng Neo4j Desktop: chạy setup_neo4j.cypher (Phương án A).\n"
                "    - Nếu dùng Community Edition đứng riêng: KHÔNG tạo được database\n"
                "      mới (đây là tính năng Enterprise). Sửa .env thành\n"
                "      NEO4J_DATABASE=neo4j rồi chạy lại (Phương án B).",
                file=sys.stderr,
            )
        elif "unsupported administration command" in lowered:
            print(
                "\n>>> Phiên bản Neo4j này là Community Edition — không tạo được\n"
                "    database riêng. Sửa .env thành NEO4J_DATABASE=neo4j (Phương án B\n"
                "    trong setup_neo4j.cypher).",
                file=sys.stderr,
            )
        elif "authentication" in lowered or "unauthorized" in lowered:
            print(
                "\n>>> Sai tài khoản hoặc mật khẩu. Kiểm tra NEO4J_USER / NEO4J_PASSWORD\n"
                "    trong .env (mật khẩu là cái anh đặt khi tạo DBMS).",
                file=sys.stderr,
            )
        else:
            print(
                "\nKiểm tra theo thứ tự:\n"
                "  1. Neo4j Desktop đã bấm Start, trạng thái Active?\n"
                "  2. Database đã tạo chưa? (chạy setup_neo4j.cypher)\n"
                "  3. Mật khẩu trong .env có đúng không?\n"
                "  4. Cổng 7687 có bị phần mềm khác chiếm không?",
                file=sys.stderr,
            )
        return 5
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
