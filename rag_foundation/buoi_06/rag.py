"""rag.py — Lõi RAG cho Buổi 6: index() / ask() / status().

Luồng: JSON chunks (Buổi 5, CHỈ ĐỌC) -> PostgreSQL (text + metadata, fallback
SQLite cục bộ khi chưa có Postgres) + ChromaDB (vector embedding) -> Gemini
(embedding + trả lời).

Chạy trực tiếp `python rag.py` để xem báo cáo môi trường (package, Python
interpreter, trạng thái ChromaDB/PostgreSQL) — dùng cho Bước 3 của bài thực hành.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Chỉ đọc JSON chunk đã có sẵn của Buổi 5 — không đụng tới code Buổi 5.
CHUNKS_DIR = BASE_DIR.parent / "buoi_05" / "output" / "chunks"
STORAGE_DIR = BASE_DIR / "storage"
CHROMA_DIR = STORAGE_DIR / "chroma"
LOCAL_DB_PATH = STORAGE_DIR / "local_fallback.db"

COLLECTION_NAME = "buoi06_chunks"
EMBED_DIM = 384
EMBED_MODEL = "gemini-embedding-2"
CHAT_MODEL = "gemini-flash-lite-latest"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "rag_db")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    source TEXT,
    strategy TEXT,
    page_start INTEGER,
    page_end INTEGER,
    structure_path TEXT,
    text TEXT
)
"""


# ---------------------------------------------------------------------------
# Gemini (lazy client — không bao giờ in giá trị API key)
# ---------------------------------------------------------------------------


def has_gemini_key() -> bool:
    return bool(GEMINI_API_KEY)


def _gemini_client():
    from google import genai

    return genai.Client(api_key=GEMINI_API_KEY)


EMBED_BATCH_SIZE = 100  # tối đa mỗi lần gọi embed_content, tránh vượt quota free tier (100 RPM)


def _embed_batch_with_retry(client, texts: list[str], config, max_retries: int = 5) -> list[list[float]]:
    """Gọi embed_content cho 1 batch, tự retry khi bị 429 (rate limit)."""
    import re
    import time

    for attempt in range(max_retries):
        try:
            resp = client.models.embed_content(model=EMBED_MODEL, contents=texts, config=config)
            return [e.values for e in resp.embeddings]
        except Exception as exc:
            msg = str(exc)
            if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                raise
            m = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)", msg)
            delay = int(m.group(1)) + 1 if m else 2**attempt
            print(f"[Gemini] Bị giới hạn tốc độ (429), chờ {delay}s rồi thử lại (lần {attempt + 1}/{max_retries})...")
            time.sleep(delay)
    raise RuntimeError(f"Gọi embed_content thất bại sau {max_retries} lần retry (vẫn bị 429).")


def _embed_texts_gemini(texts: list[str]) -> list[list[float]]:
    """Embed danh sách text theo batch (tối đa EMBED_BATCH_SIZE/lần) để không vượt quota."""
    from google.genai import types

    import time

    client = _gemini_client()
    config = types.EmbedContentConfig(output_dimensionality=EMBED_DIM)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        vectors.extend(_embed_batch_with_retry(client, batch, config))
        time.sleep(0.5)  # đệm an toàn giữa các batch, tránh sát ngưỡng RPM free tier
    return vectors


def _embed_text_fallback(text: str) -> list[float]:
    """Fallback khi THIẾU GEMINI_API_KEY lúc hỏi: dùng embedding mặc định của
    ChromaDB (all-MiniLM-L6-v2, 384 chiều). CHỈ dùng cho retrieval ở chế độ
    suy giảm — không cùng không gian ngữ nghĩa với embedding Gemini dùng lúc
    index(), nên kết quả chỉ mang tính minh hoạ (xem SPEC_buoi_06.md)."""
    from chromadb.utils import embedding_functions

    ef = embedding_functions.DefaultEmbeddingFunction()
    return ef([text])[0]


# ---------------------------------------------------------------------------
# ChromaDB: ưu tiên Server, fallback Embedded Persistent Client
# ---------------------------------------------------------------------------


def _chroma_client():
    import chromadb

    try:
        client = chromadb.HttpClient(host="localhost", port=8000)
        client.heartbeat()
        return client, "server"
    except Exception:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return client, "embedded"


def _get_collection():
    client, mode = _chroma_client()
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=None)
    return collection, mode


# ---------------------------------------------------------------------------
# PostgreSQL (ưu tiên) / SQLite cục bộ (fallback)
# ---------------------------------------------------------------------------


def _postgres_available() -> bool:
    try:
        import psycopg

        with psycopg.connect(
            host=PG_HOST, port=int(PG_PORT), user=PG_USER, password=PG_PASSWORD,
            dbname="postgres", connect_timeout=3,
        ):
            return True
    except Exception:
        return False


def _ensure_postgres_db() -> None:
    import psycopg

    with psycopg.connect(
        host=PG_HOST, port=int(PG_PORT), user=PG_USER, password=PG_PASSWORD,
        dbname="postgres", autocommit=True, connect_timeout=3,
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (PG_DB,)
        ).fetchone()
        if not exists:
            conn.execute(f"CREATE DATABASE {PG_DB}")


def _pg_connect():
    import psycopg

    return psycopg.connect(
        host=PG_HOST, port=int(PG_PORT), user=PG_USER, password=PG_PASSWORD,
        dbname=PG_DB, connect_timeout=3,
    )


def _storage_backend() -> str:
    return "postgres" if _postgres_available() else "sqlite"


def _sqlite_connect():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(LOCAL_DB_PATH)


def _init_storage() -> str:
    backend = _storage_backend()
    if backend == "postgres":
        _ensure_postgres_db()
        with _pg_connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
    else:
        with _sqlite_connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
    return backend


def _save_chunks_to_storage(backend: str, chunks: list[dict]) -> None:
    rows = [
        (
            c["chunk_id"], c.get("source"), c.get("strategy"),
            c.get("page_start"), c.get("page_end"), c.get("structure_path"), c["text"],
        )
        for c in chunks
    ]
    if backend == "postgres":
        with _pg_connect() as conn:
            conn.executemany(
                """INSERT INTO chunks (chunk_id, source, strategy, page_start, page_end, structure_path, text)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (chunk_id) DO UPDATE SET text = EXCLUDED.text""",
                rows,
            )
            conn.commit()
    else:
        with _sqlite_connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?)", rows)
            conn.commit()


def _fetch_texts_by_ids(backend: str, chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    placeholder = "%s" if backend == "postgres" else "?"
    sql = (
        "SELECT chunk_id, source, strategy, page_start, page_end, structure_path, text "
        f"FROM chunks WHERE chunk_id IN ({','.join([placeholder] * len(chunk_ids))})"
    )
    if backend == "postgres":
        with _pg_connect() as conn:
            rows = conn.execute(sql, chunk_ids).fetchall()
    else:
        with _sqlite_connect() as conn:
            rows = conn.execute(sql, chunk_ids).fetchall()
    return {
        r[0]: {
            "chunk_id": r[0], "source": r[1], "strategy": r[2],
            "page_start": r[3], "page_end": r[4], "structure_path": r[5], "text": r[6],
        }
        for r in rows
    }


def _count_rows(backend: str) -> tuple[int, int]:
    sql_chunks = "SELECT COUNT(*) FROM chunks"
    sql_docs = "SELECT COUNT(DISTINCT source) FROM chunks"
    connect = _pg_connect if backend == "postgres" else _sqlite_connect
    with connect() as conn:
        n_chunks = conn.execute(sql_chunks).fetchone()[0]
        n_docs = conn.execute(sql_docs).fetchone()[0]
    return n_docs, n_chunks


# ---------------------------------------------------------------------------
# API chính: index() / ask() / status()
# ---------------------------------------------------------------------------


def _load_all_chunks() -> list[dict]:
    """Đọc mọi file JSON trong buoi_05/output/chunks/ (chỉ đọc)."""
    if not CHUNKS_DIR.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {CHUNKS_DIR} — cần chạy xong Buổi 5 (pipeline.py --write) trước."
        )
    all_chunks: list[dict] = []
    for path in sorted(CHUNKS_DIR.glob("*.json")):
        all_chunks.extend(json.loads(path.read_text(encoding="utf-8")))
    return all_chunks


def index() -> dict:
    """Đọc JSON chunks Buổi 5 -> embed bằng Gemini -> lưu PostgreSQL/SQLite + ChromaDB."""
    if not has_gemini_key():
        raise RuntimeError(
            "Thiếu GEMINI_API_KEY trong .env — cần key hợp lệ để tạo embedding khi index()."
        )

    chunks = _load_all_chunks()
    if not chunks:
        return {"indexed": 0, "message": "Không có chunk nào trong buoi_05/output/chunks/."}

    backend = _init_storage()
    _save_chunks_to_storage(backend, chunks)

    collection, chroma_mode = _get_collection()
    ids = [c["chunk_id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    vectors = _embed_texts_gemini(texts)
    collection.upsert(ids=ids, embeddings=vectors, metadatas=[{"source": c.get("source", "")} for c in chunks])

    return {"indexed": len(chunks), "storage_backend": backend, "chroma_mode": chroma_mode}


def ask(question: str, k: int = 5) -> dict:
    """Trả lời câu hỏi dựa trên top-k chunk liên quan nhất tìm được trong ChromaDB."""
    collection, _ = _get_collection()
    backend = _storage_backend()
    degraded = not has_gemini_key()

    try:
        query_vector = _embed_text_fallback(question) if degraded else _embed_texts_gemini([question])[0]
    except Exception as exc:
        hint = (
            " (chế độ suy giảm cần tải model all-MiniLM-L6-v2 ~80MB lần đầu — "
            "kiểm tra kết nối mạng)"
            if degraded
            else ""
        )
        return {"top_k": [], "answer": None, "warning": f"Lỗi tạo embedding câu hỏi: {exc}{hint}"}

    results = collection.query(query_embeddings=[query_vector], n_results=k)
    ids = results.get("ids", [[]])[0]
    texts_map = _fetch_texts_by_ids(backend, ids)
    top_k = [texts_map[i] for i in ids if i in texts_map]

    if degraded:
        return {
            "top_k": top_k,
            "answer": None,
            "warning": "Thiếu GEMINI_API_KEY — chỉ hiển thị kết quả tra cứu (retrieval), không gọi Gemini để trả lời.",
        }

    context = "\n\n".join(f"[{c['chunk_id']}] {c['text']}" for c in top_k)
    prompt = (
        "Trả lời câu hỏi sau CHỈ dựa trên ngữ cảnh cung cấp bên dưới. "
        "Nếu ngữ cảnh không đủ thông tin để trả lời, hãy nói rõ là không tìm thấy.\n\n"
        f"Ngữ cảnh:\n{context}\n\nCâu hỏi: {question}\nTrả lời:"
    )
    try:
        client = _gemini_client()
        resp = client.models.generate_content(model=CHAT_MODEL, contents=prompt)
        return {"top_k": top_k, "answer": resp.text, "warning": None}
    except Exception as exc:
        return {"top_k": top_k, "answer": None, "warning": f"Lỗi gọi Gemini: {exc}"}


def status() -> dict:
    """Trạng thái hiện tại: backend lưu trữ, số document, số chunk, chế độ ChromaDB."""
    backend = _storage_backend()
    try:
        n_docs, n_chunks = _count_rows(backend)
    except Exception:
        n_docs, n_chunks = 0, 0
    try:
        _, chroma_mode = _chroma_client()
    except Exception:
        chroma_mode = "lỗi"
    return {
        "storage_backend": backend,
        "n_documents": n_docs,
        "n_chunks": n_chunks,
        "chroma_mode": chroma_mode,
        "gemini_key_present": has_gemini_key(),
    }


# ---------------------------------------------------------------------------
# Báo cáo môi trường (Bước 3) — chạy `python rag.py`
# ---------------------------------------------------------------------------


def _check_packages() -> list[tuple[str, bool, str]]:
    results = []
    for name, module in [
        ("streamlit", "streamlit"),
        ("google-genai", "google.genai"),
        ("chromadb", "chromadb"),
        ("psycopg", "psycopg"),
        ("python-dotenv", "dotenv"),
    ]:
        try:
            __import__(module)
            results.append((name, True, "đã cài"))
        except ImportError as exc:
            results.append((name, False, str(exc)))
    return results


def _print_environment_report() -> None:
    print(f"Python interpreter: {sys.executable}\n")

    print("Kiểm tra package:")
    for name, ok, detail in _check_packages():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")

    print()
    try:
        _, chroma_mode = _chroma_client()
        label = "Server" if chroma_mode == "server" else "Embedded Local"
        print(f"ChromaDB: {label} (embedded lưu tại {CHROMA_DIR})")
    except Exception as exc:
        print(f"ChromaDB: lỗi khởi tạo — {exc}")

    print()
    if _postgres_available():
        print(f"PostgreSQL: đã kết nối được tới {PG_HOST}:{PG_PORT}")
        try:
            _ensure_postgres_db()
            print(f"Database '{PG_DB}': sẵn sàng")
        except Exception as exc:
            print(f"Database '{PG_DB}': lỗi tạo/kiểm tra — {exc}")
    else:
        print(
            "PostgreSQL: CHƯA kết nối được. Việc cần làm:\n"
            "  1. Tải PostgreSQL: https://www.postgresql.org/download/ và cài đặt.\n"
            "  2. Ghi nhớ mật khẩu user 'postgres' lúc cài.\n"
            "  3. Điền mật khẩu đó vào POSTGRES_PASSWORD trong file .env.\n"
            "  4. Chạy lại: python rag.py\n"
            f"  Trong lúc chưa có PostgreSQL, dữ liệu sẽ tự lưu vào file cục bộ: {LOCAL_DB_PATH}"
        )

    print()
    key_status = "đã cấu hình (giá trị được giữ kín)" if has_gemini_key() else "CHƯA cấu hình trong .env"
    print(f"GEMINI_API_KEY: {key_status}")


if __name__ == "__main__":
    _print_environment_report()
