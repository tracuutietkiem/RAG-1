"""
Cau hinh dung chung cho Buoi 14.

Nguyen tac:
  - Moi output cua Buoi 14 nam trong buoi_14/.
  - Du lieu nguon CHI DOC, khong sua/ghi de.
  - Khong hard-code password / API key.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- .env
def _load_dotenv(path: Path) -> None:
    """Doc .env don gian (KEY=VALUE) neu python-dotenv chua duoc cai."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# Windows thuong tu them duoi .txt khi doi ten file trong File Explorer
# (khi tuy chon "File name extensions" dang tat), nen file that su co the la
# ".env.txt". Chap nhan ca hai de nguoi dung khong phai vat lon voi Explorer.
# Doc theo thu tu uu tien; file dau tien tim thay se duoc dung.
ENV_CANDIDATES = [".env", ".env.txt"]

ENV_FILE_USED = None
for _name in ENV_CANDIDATES:
    _p = BASE_DIR / _name
    if _p.exists():
        _load_dotenv(_p)
        ENV_FILE_USED = _p
        break

# ---------------------------------------------------------------- duong dan
# De bai goc gia dinh du lieu nam o `../kb+hops/`. Tren may thuc te cua hoc vien
# bo 3 file nay nam o `../Buổi 12/ner_kb/`. Uu tien bien moi truong KB_DIR,
# sau do do lan luot cac vi tri da biet.
_KB_CANDIDATES = [
    "../kb+hops",
    "../Buổi 12/ner_kb",
    "../Buoi 12/ner_kb",
    "../buoi_12/ner_kb",
]


def _resolve_kb_dir() -> Path:
    env = os.getenv("KB_DIR")
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        return p
    for cand in _KB_CANDIDATES:
        p = (BASE_DIR / cand).resolve()
        if p.is_dir():
            return p
    return (BASE_DIR / _KB_CANDIDATES[0]).resolve()


KB_DIR = _resolve_kb_dir()
METADATA_CSV = KB_DIR / "metadata.csv"
CONTENT_CSV = KB_DIR / "content.csv"
RELATIONSHIPS_CSV = KB_DIR / "relationships.csv"

DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
EVAL_DIR = DATA_DIR / "eval"
CACHE_DIR = BASE_DIR / "cache"
OUTPUTS_DIR = BASE_DIR / "outputs"

CHUNKS_CSV = PROCESSED_DIR / "chunks_normalized.csv"
QUESTIONS_CSV = EVAL_DIR / "questions.csv"

for _d in (PROCESSED_DIR, EVAL_DIR, CACHE_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- tham so
def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Chunking
MAX_CHUNK_CHARS = _int("MAX_CHUNK_CHARS", 3000)
MIN_CHUNK_CHARS = _int("MIN_CHUNK_CHARS", 40)

# Retrieval
BM25_CANDIDATES = _int("BM25_CANDIDATES", 20)
DENSE_CANDIDATES = _int("DENSE_CANDIDATES", 20)
CANDIDATE_K = _int("CANDIDATE_K", 20)
FINAL_TOP_K = _int("FINAL_TOP_K", 5)
RRF_K = _int("RRF_K", 60)
RRF_BM25_WEIGHT = _float("RRF_BM25_WEIGHT", 1.0)
RRF_DENSE_WEIGHT = _float("RRF_DENSE_WEIGHT", 1.0)

# Dense backend: "auto" | "sentence_transformers" | "lsa"
DENSE_BACKEND = os.getenv("DENSE_BACKEND", "auto").strip().lower()
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5"
)
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
LSA_DIM = _int("LSA_DIM", 256)

# Rerank backend: "auto" | "cross_encoder" | "fallback"
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "auto").strip().lower()
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_MAX_LENGTH = _int("RERANKER_MAX_LENGTH", 512)
RERANK_BATCH_SIZE = _int("RERANK_BATCH_SIZE", 4)
RERANK_DEVICE = os.getenv("RERANK_DEVICE", "cpu")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

LAB_SESSION = "buoi_14"
