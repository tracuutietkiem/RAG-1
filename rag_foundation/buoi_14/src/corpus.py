"""Doc corpus da chuan hoa. Ca BM25, Dense, Hybrid, Reranker deu dung ham nay
-> dam bao KHONG co chuyen hai retriever chay tren hai tap du lieu khac nhau."""

import csv
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


@lru_cache(maxsize=1)
def load_chunks() -> tuple[dict, ...]:
    """Tra ve tuple cac chunk (immutable de cache duoc)."""
    path = config.CHUNKS_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"Chua co {path}. Chay truoc: python scripts/prepare_corpus.py"
        )
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise RuntimeError(f"{path} rong")
    return tuple(rows)


@lru_cache(maxsize=1)
def chunk_index() -> dict:
    """chunk_id -> record."""
    return {r["chunk_id"]: r for r in load_chunks()}


def corpus_fingerprint() -> str:
    """Van tay corpus de invalid cache embedding khi corpus doi."""
    import hashlib

    h = hashlib.sha256()
    for r in load_chunks():
        h.update(r["chunk_id"].encode("utf-8"))
        h.update(str(len(r["text"])).encode("utf-8"))
    return h.hexdigest()[:16]


def index_text_of(rec: dict) -> str:
    """Text dung de INDEX (co header dinh danh van ban). Neu corpus cu chua co
    cot index_text thi dung lai `text` - khong lam vo tuong thich."""
    return (rec.get("index_text") or "").strip() or rec.get("text", "")
