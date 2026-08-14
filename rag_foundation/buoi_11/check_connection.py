"""Kiểm tra kết nối Neo4j trước khi chạy `setup-index`/`ask`/`compare` — chạy
trong vài giây, không ghi gì. Bản sao rút gọn từ `buoi_10/check_connection.py`.

Chạy: python check_connection.py
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from src.graph_search import Neo4jConfig, default_driver_factory


def main() -> int:
    load_dotenv()
    config = Neo4jConfig.from_env()

    print(f"URI      : {config.uri}")
    print(f"Database : {config.database}")
    print(f"Password : {'(đã điền)' if config.password else '(TRỐNG — kiểm tra .env)'}")
    print("-" * 50)

    if not config.password:
        print("LỖI: NEO4J_PASSWORD trống. Mở file .env và điền mật khẩu.", file=sys.stderr)
        return 2

    try:
        driver = default_driver_factory(config)
    except Exception as exc:  # noqa: BLE001
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
        for row in counts:
            print(f"  {row['labels']}: {row['n']}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"LỖI khi kết nối/truy vấn: {exc}", file=sys.stderr)
        print(
            "\nKiểm tra: Neo4j Desktop đã Start chưa? Database 'kb-hops' đã tạo "
            "chưa (Buổi 10)? Mật khẩu trong .env đúng chưa?",
            file=sys.stderr,
        )
        return 5
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
