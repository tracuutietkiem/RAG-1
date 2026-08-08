"""rag.py — Lõi RAG cho Buổi 07.

Pipeline hoàn chỉnh:

    Chunks JSON của Buổi 05 (chỉ đọc)
        -> validate (Bước 04 — ĐÃ CÓ)
        -> Gemini embedding (Bước 05 — ĐÃ CÓ)
        -> ChromaDB persistent index (Bước 05 — ĐÃ CÓ)
        -> semantic retrieval top-k (Bước 06 — ĐÃ CÓ)
        -> confidence gate theo RAG_MAX_DISTANCE (Bước 06 — ĐÃ CÓ)
        -> Gemini tổng hợp câu trả lời có grounding (Bước 06 — ĐÃ CÓ)
        -> citation map từ metadata thật (Bước 06 — ĐÃ CÓ)

Xem đầy đủ ràng buộc tại SPEC_buoi_07.md.

CLI hiện có:

    <PYTHON> rag.py validate --strategy hierarchical
    <PYTHON> rag.py status --strategy hierarchical
    <PYTHON> rag.py index --strategy hierarchical [--reset]
    <PYTHON> rag.py query --strategy hierarchical --question "..." [--top-k N]

Trạng thái hiện tại: Bước 07 — có loader/validator (Bước 04), embedding
Gemini + ChromaDB persistent index (Bước 05), retrieval + confidence gate +
generation + citation map (Bước 06), giao diện Streamlit `app.py` (Bước 07).
Bộ test tự động (`tests/test_rag.py`, Bước 08) đã có, 69 test case, chạy
offline hoàn toàn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path & cấu hình (không hard-code đường dẫn theo máy)
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CHUNKS_DIR = BASE_DIR.parent / "buoi_05" / "output" / "chunks"
ENV_PATH = BASE_DIR / ".env"
CHROMA_DIR = BASE_DIR / "storage" / "chroma"

# Buổi 07 chuẩn hoá tên strategy dùng dấu gạch ngang. Dữ liệu thật của Buổi 05
# lại dùng "fixed_size" (gạch dưới) — xem SPEC_buoi_07.md mục Input.
VALID_STRATEGIES = ("fixed-size", "semantic", "hierarchical")
STRATEGY_ALIASES = {"fixed_size": "fixed-size"}
DEFAULT_STRATEGY = "hierarchical"

REQUIRED_FIELDS = ["chunk_id", "strategy", "source", "page_start", "page_end", "text"]

SCHEMA_VERSION = 1
DISTANCE_METRIC = "cosine"


class DataError(ValueError):
    """Lỗi dữ liệu đầu vào (JSON hỏng, thiếu field, sai kiểu, ...) — thông báo dễ đọc."""


class ConfigError(ValueError):
    """Lỗi cấu hình (.env) — thông báo dễ đọc, KHÔNG bao giờ in giá trị secret."""


class EmbeddingError(ValueError):
    """Lỗi liên quan tới embedding (thiếu key, vector không hợp lệ, gọi API lỗi, ...)."""


class ChromaError(ValueError):
    """Lỗi liên quan tới ChromaDB (metadata/config không khớp, ...)."""


def _normalize_strategy(value):
    """Chuẩn hoá tên strategy về dạng gạch ngang; không đổi nếu value không phải string."""
    if not isinstance(value, str):
        return value
    return STRATEGY_ALIASES.get(value, value)


# ---------------------------------------------------------------------------
# Loader (Bước 04)
# ---------------------------------------------------------------------------


def _read_json_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataError(f"Không đọc được file '{path.name}': {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError(f"File '{path.name}' không phải JSON hợp lệ: {exc}") from exc


def _extract_records(data, filename: str) -> list:
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and isinstance(data.get("chunks"), list):
        records = data["chunks"]
    else:
        raise DataError(
            f"File '{filename}' phải là JSON list, hoặc JSON object có field "
            "'chunks' kiểu list. Cấu trúc hiện tại không hợp lệ."
        )
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise DataError(
                f"File '{filename}', record vị trí {i}: phải là JSON object, "
                f"nhận kiểu {type(r).__name__}."
            )
    return records


def validate_chunk(record: dict, filename: str, index: int) -> dict:
    """
    Validate 1 record thô theo Data Contract (xem SPEC_buoi_07.md).

    Trả về OBJECT MỚI (không sửa `record` gốc tại chỗ) với strategy đã chuẩn
    hoá và text đã strip. Giữ nguyên mọi field metadata khác có trong record
    gốc (vd `structure_path`, `structure_detected`).

    Raise DataError với thông báo dễ đọc, có tên file + vị trí record, khi
    dữ liệu sai (thiếu field, sai kiểu, page không hợp lệ, strategy không hợp lệ).
    """
    location = f"file '{filename}', record vị trí {index}"

    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        raise DataError(f"{location}: thiếu field bắt buộc {missing}.")

    chunk_id = record["chunk_id"]
    strategy_raw = record["strategy"]
    source = record["source"]
    text = record["text"]
    page_start = record["page_start"]
    page_end = record["page_end"]

    for field_name, value in [
        ("chunk_id", chunk_id),
        ("strategy", strategy_raw),
        ("source", source),
        ("text", text),
    ]:
        if not isinstance(value, str):
            raise DataError(
                f"{location}: field '{field_name}' phải là string, nhận kiểu {type(value).__name__}."
            )

    for field_name, value in [("chunk_id", chunk_id), ("strategy", strategy_raw), ("source", source)]:
        if not value.strip():
            raise DataError(f"{location}: field '{field_name}' không được rỗng sau strip().")

    strategy = _normalize_strategy(strategy_raw)
    if strategy not in VALID_STRATEGIES:
        raise DataError(
            f"{location}: strategy '{strategy_raw}' không hợp lệ "
            f"(chỉ nhận {', '.join(VALID_STRATEGIES)})."
        )

    for field_name, value in [("page_start", page_start), ("page_end", page_end)]:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DataError(
                f"{location}: field '{field_name}' phải là số nguyên (không chấp nhận boolean), "
                f"nhận kiểu {type(value).__name__}."
            )
        if value < 1:
            raise DataError(f"{location}: field '{field_name}' phải >= 1, nhận {value}.")
    if page_start > page_end:
        raise DataError(f"{location}: page_start ({page_start}) phải <= page_end ({page_end}).")

    result = dict(record)  # object mới — không sửa record gốc
    result["strategy"] = strategy
    result["text"] = text.strip()
    return result


def load_chunks(input_dir: Path = CHUNKS_DIR, strategy: str = DEFAULT_STRATEGY) -> tuple[list, dict]:
    """
    Đọc toàn bộ file .json trong `input_dir`, chỉ giữ đúng 1 `strategy`.

    Trả về (valid_chunks, stats). KHÔNG sửa dữ liệu nguồn. Raise DataError với
    thông báo rõ ràng khi: thiếu thư mục, không có file JSON, JSON lỗi, sai
    cấu trúc, record không phải object, thiếu field, sai kiểu, trang không
    hợp lệ, strategy không hợp lệ, hoặc trùng chunk_id.
    """
    if strategy not in VALID_STRATEGIES:
        raise DataError(
            f"strategy '{strategy}' không hợp lệ (chỉ nhận {', '.join(VALID_STRATEGIES)})."
        )

    if not input_dir.exists() or not input_dir.is_dir():
        raise DataError(f"Không tìm thấy thư mục dữ liệu: {input_dir}")

    files = sorted(input_dir.glob("*.json"))
    if not files:
        raise DataError(f"Không có file .json nào trong: {input_dir}")

    valid_chunks: list[dict] = []
    seen_ids: dict[str, tuple[str, int]] = {}
    total_records = 0
    selected_records = 0
    empty_text_skipped = 0

    for path in files:
        data = _read_json_file(path)
        records = _extract_records(data, path.name)
        total_records += len(records)

        for i, raw in enumerate(records):
            if _normalize_strategy(raw.get("strategy")) != strategy:
                continue
            selected_records += 1

            chunk = validate_chunk(raw, path.name, i)

            cid = chunk["chunk_id"]
            if cid in seen_ids:
                first_file, first_idx = seen_ids[cid]
                raise DataError(
                    f"chunk_id trùng lặp '{cid}': lần đầu ở file '{first_file}' vị trí {first_idx}, "
                    f"lần hai ở file '{path.name}' vị trí {i}."
                )
            seen_ids[cid] = (path.name, i)

            if not chunk["text"]:
                empty_text_skipped += 1
                continue

            valid_chunks.append(chunk)

    stats = {
        "files_read": len(files),
        "total_records": total_records,
        "selected_records": selected_records,
        "empty_text_skipped": empty_text_skipped,
        "valid_chunks": len(valid_chunks),
    }
    return valid_chunks, stats


# ---------------------------------------------------------------------------
# Config (Bước 05) — đọc .env, validate, KHÔNG bao giờ in secret ra log
# ---------------------------------------------------------------------------


@dataclass
class Config:
    gemini_api_key: str
    embedding_model: str
    embedding_dim: int
    generation_model: str
    default_top_k: int
    max_distance: float


def load_config(env_path: Path = ENV_PATH) -> Config:
    """
    Đọc `.env` + validate. `gemini_api_key` rỗng KHÔNG phải lỗi ở bước này —
    chỉ lệnh nào thực sự cần gọi Gemini (vd `index`) mới raise EmbeddingError
    khi thiếu key.
    """
    load_dotenv(env_path, override=True)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "").strip()
    generation_model = os.getenv("GEMINI_GENERATION_MODEL", "").strip()
    dim_raw = os.getenv("GEMINI_EMBEDDING_DIM", "").strip()
    top_k_raw = os.getenv("DEFAULT_TOP_K", "").strip()
    max_dist_raw = os.getenv("RAG_MAX_DISTANCE", "").strip()

    if not embedding_model:
        raise ConfigError("Thiếu GEMINI_EMBEDDING_MODEL trong .env.")
    if not generation_model:
        raise ConfigError("Thiếu GEMINI_GENERATION_MODEL trong .env.")

    try:
        embedding_dim = int(dim_raw)
    except (TypeError, ValueError):
        raise ConfigError(f"GEMINI_EMBEDDING_DIM phải là số nguyên, nhận '{dim_raw}'.") from None
    if not (128 <= embedding_dim <= 3072):
        raise ConfigError(f"GEMINI_EMBEDDING_DIM phải trong khoảng 128-3072, nhận {embedding_dim}.")

    try:
        default_top_k = int(top_k_raw)
    except (TypeError, ValueError):
        raise ConfigError(f"DEFAULT_TOP_K phải là số nguyên, nhận '{top_k_raw}'.") from None
    if not (1 <= default_top_k <= 20):
        raise ConfigError(f"DEFAULT_TOP_K phải trong khoảng 1-20, nhận {default_top_k}.")

    try:
        max_distance = float(max_dist_raw)
    except (TypeError, ValueError):
        raise ConfigError(f"RAG_MAX_DISTANCE phải là số thực, nhận '{max_dist_raw}'.") from None
    if max_distance < 0:
        raise ConfigError(f"RAG_MAX_DISTANCE phải >= 0, nhận {max_distance}.")

    return Config(
        gemini_api_key=api_key,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        generation_model=generation_model,
        default_top_k=default_top_k,
        max_distance=max_distance,
    )


# ---------------------------------------------------------------------------
# Gemini embedding (Bước 05) — inject được client_factory để test offline
# ---------------------------------------------------------------------------


def _default_gemini_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def _embed_one(client, formatted_text: str, config: Config) -> list:
    from google.genai import types

    response = client.models.embed_content(
        model=config.embedding_model,
        contents=formatted_text,
        config=types.EmbedContentConfig(output_dimensionality=config.embedding_dim),
    )
    return list(response.embeddings[0].values)


def embed_documents(chunks: list[dict], config: Config, client_factory=_default_gemini_client) -> list:
    """
    Tạo 1 vector / chunk. Input format theo SPEC: "title: <source> | text: <text>".
    Gọi tuần tự (không batch, không retry) theo đúng yêu cầu Bước 05.
    """
    if not config.gemini_api_key:
        raise EmbeddingError("Thiếu GEMINI_API_KEY trong .env — không thể tạo embedding thật.")
    try:
        client = client_factory(config.gemini_api_key)
    except Exception as exc:
        raise EmbeddingError(f"Khởi tạo Gemini client thất bại: {exc}") from exc
    vectors = []
    for chunk in chunks:
        formatted = f"title: {chunk['source']} | text: {chunk['text']}"
        try:
            vectors.append(_embed_one(client, formatted, config))
        except EmbeddingError:
            raise
        except Exception as exc:  # lỗi gọi API thật (mạng, quota, key sai, ...)
            raise EmbeddingError(f"Gọi Gemini embedding lỗi cho chunk '{chunk.get('chunk_id')}': {exc}") from exc
    return vectors


def embed_query(question: str, config: Config, client_factory=_default_gemini_client) -> list:
    """Input format theo SPEC: "task: question answering | query: <question>"."""
    if not config.gemini_api_key:
        raise EmbeddingError("Thiếu GEMINI_API_KEY trong .env — không thể tạo embedding thật.")
    try:
        client = client_factory(config.gemini_api_key)
    except Exception as exc:
        raise EmbeddingError(f"Khởi tạo Gemini client thất bại: {exc}") from exc
    formatted = f"task: question answering | query: {question}"
    try:
        return _embed_one(client, formatted, config)
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(f"Gọi Gemini embedding lỗi cho câu hỏi: {exc}") from exc


def validate_embeddings(vectors: list, expected_count: int, expected_dim: int) -> None:
    """
    Validate TOÀN BỘ vector trước khi cho phép upsert/reset. Raise EmbeddingError
    với thông báo rõ ràng ngay khi gặp vector đầu tiên không hợp lệ.
    """
    if len(vectors) != expected_count:
        raise EmbeddingError(
            f"Số vector nhận được ({len(vectors)}) khác số chunk cần embed ({expected_count})."
        )

    for i, v in enumerate(vectors):
        if not isinstance(v, list) or len(v) == 0:
            raise EmbeddingError(f"Vector #{i}: rỗng hoặc không phải list.")
        if len(v) != expected_dim:
            raise EmbeddingError(f"Vector #{i}: sai dimension ({len(v)} != {expected_dim}).")

        has_nonzero = False
        for j, x in enumerate(v):
            if isinstance(x, bool):
                raise EmbeddingError(f"Vector #{i}, phần tử #{j}: là boolean — không hợp lệ.")
            if not isinstance(x, (int, float)):
                raise EmbeddingError(
                    f"Vector #{i}, phần tử #{j}: không phải số (kiểu {type(x).__name__})."
                )
            fx = float(x)
            if math.isnan(fx):
                raise EmbeddingError(f"Vector #{i}, phần tử #{j}: là NaN.")
            if math.isinf(fx):
                raise EmbeddingError(f"Vector #{i}, phần tử #{j}: là Infinity.")
            if fx != 0.0:
                has_nonzero = True

        if not has_nonzero:
            raise EmbeddingError(f"Vector #{i}: là zero-vector toàn số 0 — không hợp lệ.")


# ---------------------------------------------------------------------------
# ChromaDB (Bước 05)
# ---------------------------------------------------------------------------


def collection_name(strategy: str, dim: int, model: str) -> str:
    """
    Tên collection duy nhất theo strategy + dimension + hash ổn định của tên
    model (KHÔNG hard-code hash mẫu — tính động bằng sha256).
    """
    model_hash = hashlib.sha256(model.encode("utf-8")).hexdigest()[:8]
    safe_strategy = strategy.replace("_", "-")
    return f"nhnn-{safe_strategy}-{dim}-{model_hash}"


def _chroma_client(persist_path: Path = CHROMA_DIR):
    import chromadb

    persist_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_path))


def _list_collection_names(client) -> list[str]:
    existing = client.list_collections()
    return [c.name if hasattr(c, "name") else c for c in existing]


def _expected_collection_metadata(strategy: str, config: Config) -> dict:
    return {
        "strategy": strategy,
        "embedding_model": config.embedding_model,
        "embedding_dim": config.embedding_dim,
        "distance_metric": DISTANCE_METRIC,
        "schema_version": SCHEMA_VERSION,
    }


def _verify_collection_metadata(collection, strategy: str, config: Config) -> None:
    meta = collection.metadata or {}
    expected = _expected_collection_metadata(strategy, config)
    mismatches = [
        f"{k}: kỳ vọng {v!r}, thực tế {meta.get(k)!r}" for k, v in expected.items() if meta.get(k) != v
    ]
    if mismatches:
        raise ChromaError(
            "Collection đã tồn tại nhưng metadata không khớp cấu hình hiện tại: "
            + "; ".join(mismatches)
            + ". Chạy lại lệnh 'index' với --reset để tạo lại collection đúng cấu hình."
        )


def get_status(strategy: str, config: Config, persist_path: Path = CHROMA_DIR) -> dict:
    """Chỉ đọc: KHÔNG tạo collection, KHÔNG gọi Gemini."""
    name = collection_name(strategy, config.embedding_dim, config.embedding_model)
    client = _chroma_client(persist_path)
    names = _list_collection_names(client)
    exists = name in names
    record_count = 0
    metadata_ok = None
    if exists:
        col = client.get_collection(name=name, embedding_function=None)
        record_count = col.count()
        try:
            _verify_collection_metadata(col, strategy, config)
            metadata_ok = True
        except ChromaError:
            metadata_ok = False

    return {
        "api_key_present": bool(config.gemini_api_key),
        "embedding_model": config.embedding_model,
        "embedding_dim": config.embedding_dim,
        "strategy": strategy,
        "collection_name": name,
        "collection_exists": exists,
        "record_count": record_count,
        "metadata_ok": metadata_ok,
    }


def index_chunks(
    strategy: str,
    config: Config,
    reset: bool = False,
    chunks_dir: Path = CHUNKS_DIR,
    persist_path: Path = CHROMA_DIR,
    client_factory=_default_gemini_client,
) -> dict:
    """
    Load -> embed toàn bộ -> validate toàn bộ -> (chỉ sau khi validate OK)
    mới đụng tới ChromaDB. --reset chỉ xoá đúng collection đích, và chỉ xoá
    SAU KHI embedding đã được validate thành công. Idempotent qua upsert
    theo chunk_id (chạy lại không tăng record_count).
    """
    if not config.gemini_api_key:
        raise EmbeddingError("Thiếu GEMINI_API_KEY trong .env — không thể index (cần embedding thật).")

    chunks, load_stats = load_chunks(input_dir=chunks_dir, strategy=strategy)
    if not chunks:
        raise DataError(f"Không có chunk hợp lệ nào cho strategy '{strategy}' để index.")

    vectors = embed_documents(chunks, config, client_factory=client_factory)
    validate_embeddings(vectors, expected_count=len(chunks), expected_dim=config.embedding_dim)

    name = collection_name(strategy, config.embedding_dim, config.embedding_model)
    client = _chroma_client(persist_path)
    names = _list_collection_names(client)
    exists = name in names

    if exists:
        if reset:
            client.delete_collection(name=name)
            exists = False
        else:
            existing_col = client.get_collection(name=name, embedding_function=None)
            _verify_collection_metadata(existing_col, strategy, config)

    col = client.get_or_create_collection(
        name=name,
        embedding_function=None,
        configuration={"hnsw": {"space": DISTANCE_METRIC}},
        metadata=_expected_collection_metadata(strategy, config),
    )
    if exists:
        # Collection đã tồn tại trước đó và không reset -> đã verify ở trên,
        # nhưng verify lại 1 lần nữa cho chắc trước khi ghi dữ liệu thật.
        _verify_collection_metadata(col, strategy, config)

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "chunk_id": c["chunk_id"],
            "source": c["source"],
            "strategy": c["strategy"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
        }
        for c in chunks
    ]

    col.upsert(ids=ids, embeddings=vectors, documents=documents, metadatas=metadatas)

    return {
        "collection": name,
        "reset": reset,
        "chunks_embedded": len(chunks),
        "record_count": col.count(),
        **load_stats,
    }


# ---------------------------------------------------------------------------
# Retrieval + confidence gate (Bước 06)
# ---------------------------------------------------------------------------


def _build_evidence(query_result: dict, config: Config) -> list[dict]:
    ids = query_result.get("ids", [[]])[0]
    documents = query_result.get("documents", [[]])[0]
    metadatas = query_result.get("metadatas", [[]])[0]
    distances = query_result.get("distances", [[]])[0]

    evidence = []
    for i, (cid, doc, meta, dist) in enumerate(zip(ids, documents, metadatas, distances)):
        meta = meta or {}
        evidence.append(
            {
                "label": f"E{i + 1}",
                "chunk_id": meta.get("chunk_id", cid),
                "source": meta.get("source"),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "text": doc,
                "distance": float(dist),
                "accepted": float(dist) <= config.max_distance,
            }
        )
    return evidence


def retrieve(
    question: str,
    strategy: str,
    config: Config,
    top_k: int | None = None,
    persist_path: Path = CHROMA_DIR,
    client_factory=_default_gemini_client,
) -> list[dict]:
    """
    Truy vấn semantic top-k qua Chroma. Trả evidence THẬT kèm `distance` lấy
    trực tiếp từ Chroma (không tự chế điểm số). Raise ChromaError nếu
    collection chưa tồn tại hoặc metadata không khớp cấu hình hiện tại.
    """
    if not question or not question.strip():
        raise DataError("Câu hỏi rỗng — không thể truy vấn.")

    top_k = top_k or config.default_top_k

    name = collection_name(strategy, config.embedding_dim, config.embedding_model)
    client = _chroma_client(persist_path)
    if name not in _list_collection_names(client):
        raise ChromaError(
            f"Collection '{name}' chưa tồn tại — hãy chạy lệnh 'index --strategy {strategy}' trước."
        )
    col = client.get_collection(name=name, embedding_function=None)
    _verify_collection_metadata(col, strategy, config)

    query_vector = embed_query(question, config, client_factory=client_factory)
    result = col.query(query_embeddings=[query_vector], n_results=top_k)
    return _build_evidence(result, config)


# ---------------------------------------------------------------------------
# Generation + citation (Bước 06)
# ---------------------------------------------------------------------------

_CITATION_PATTERN = re.compile(r"\[E(\d+)\]")


def generate_answer(
    question: str,
    accepted_evidence: list[dict],
    config: Config,
    client_factory=_default_gemini_client,
) -> str:
    """
    Sinh câu trả lời CHỈ dựa trên `accepted_evidence` (đã qua confidence gate).
    Yêu cầu LLM chèn nhãn trích dẫn [E#] đúng theo nhãn evidence được cấp —
    việc map nhãn -> metadata thật do code xử lý ở `_extract_citations`,
    KHÔNG tin bất kỳ source/page/chunk_id nào LLM tự viết trong văn bản.
    """
    if not config.gemini_api_key:
        raise EmbeddingError("Thiếu GEMINI_API_KEY trong .env — không thể sinh câu trả lời.")

    try:
        client = client_factory(config.gemini_api_key)
    except Exception as exc:
        raise EmbeddingError(f"Khởi tạo Gemini client thất bại: {exc}") from exc

    context_blocks = [
        f"[{e['label']}] (nguồn: {e['source']}, trang {e['page_start']}-{e['page_end']})\n{e['text']}"
        for e in accepted_evidence
    ]
    context = "\n\n".join(context_blocks)

    prompt = (
        "Bạn là trợ lý trả lời câu hỏi nghiệp vụ, CHỈ được dùng thông tin trong các đoạn "
        "trích dẫn dưới đây, không dùng kiến thức ngoài đoạn trích. Khi dùng thông tin từ "
        "đoạn nào, chèn đúng nhãn trích dẫn của đoạn đó (dạng [E1], [E2], ...) ngay sau câu "
        "liên quan. Nếu các đoạn trích không đủ để trả lời chắc chắn, hãy nói rõ là không đủ "
        "căn cứ thay vì suy đoán.\n\n"
        f"Các đoạn trích:\n{context}\n\n"
        f"Câu hỏi: {question}\n\nTrả lời:"
    )

    try:
        response = client.models.generate_content(model=config.generation_model, contents=prompt)
    except Exception as exc:  # lỗi gọi API thật (mạng, quota, key sai, ...)
        raise EmbeddingError(f"Gọi Gemini generation lỗi: {exc}") from exc

    text = getattr(response, "text", None) or ""
    return text.strip()


def _extract_citations(answer: str, accepted_evidence: list[dict]) -> tuple[str, list[dict], list[str]]:
    valid = {e["label"]: e for e in accepted_evidence}
    warnings: list[str] = []
    used_labels: list[str] = []

    def _replace(match: re.Match) -> str:
        label = f"E{match.group(1)}"
        if label in valid:
            if label not in used_labels:
                used_labels.append(label)
            return f"[{label}]"
        warnings.append(f"Nhãn trích dẫn không hợp lệ '[{label}]' do model sinh ra — đã loại khỏi câu trả lời.")
        return ""

    cleaned = _CITATION_PATTERN.sub(_replace, answer)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    citations = []
    for label in used_labels:
        e = valid[label]
        citations.append(
            {
                "label": label,
                "chunk_id": e["chunk_id"],
                "source": e["source"],
                "page_start": e["page_start"],
                "page_end": e["page_end"],
                "distance": e["distance"],
            }
        )
    return cleaned, citations, warnings


def ask(
    question: str,
    strategy: str,
    config: Config,
    top_k: int | None = None,
    persist_path: Path = CHROMA_DIR,
    embed_client_factory=_default_gemini_client,
    generation_client_factory=_default_gemini_client,
) -> dict:
    """
    Pipeline đầy đủ: retrieve -> confidence gate -> generation (nếu đủ căn cứ)
    -> citation map từ metadata thật. Luôn trả đủ field:
    status/answer/evidence/citations/warnings/collection/strategy/top_k.

    status:
      - "insufficient_evidence": không evidence nào đạt RAG_MAX_DISTANCE,
        KHÔNG gọi Gemini generation.
      - "retrieval_only": có evidence đạt ngưỡng nhưng bước generation lỗi
        hoặc trả về rỗng — vẫn trả evidence/citations rỗng, không giả vờ có
        câu trả lời.
      - "answered": generation thành công, có câu trả lời + citation map.

    Thiếu GEMINI_API_KEY khi cần embed câu hỏi sẽ raise EmbeddingError (không
    dùng vector giả cho query) — nhất quán với hành vi của lệnh `index`.
    """
    top_k = top_k or config.default_top_k
    name = collection_name(strategy, config.embedding_dim, config.embedding_model)
    warnings: list[str] = []

    evidence = retrieve(
        question, strategy, config, top_k=top_k, persist_path=persist_path, client_factory=embed_client_factory
    )
    accepted = [e for e in evidence if e["accepted"]]

    result = {
        "status": None,
        "answer": None,
        "evidence": evidence,
        "citations": [],
        "warnings": warnings,
        "collection": name,
        "strategy": strategy,
        "top_k": top_k,
    }

    if not accepted:
        result["status"] = "insufficient_evidence"
        warnings.append(f"Không có evidence nào đạt ngưỡng RAG_MAX_DISTANCE={config.max_distance}.")
        return result

    try:
        raw_answer = generate_answer(question, accepted, config, client_factory=generation_client_factory)
        if not raw_answer:
            raise EmbeddingError("Gemini trả về câu trả lời rỗng.")
    except Exception as exc:
        result["status"] = "retrieval_only"
        warnings.append(f"Sinh câu trả lời thất bại: {exc}")
        return result

    cleaned_answer, citations, citation_warnings = _extract_citations(raw_answer, accepted)
    result["answer"] = cleaned_answer
    result["citations"] = citations
    warnings.extend(citation_warnings)
    result["status"] = "answered"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_validate(strategy: str, input_dir: Path = CHUNKS_DIR) -> int:
    try:
        chunks, stats = load_chunks(input_dir=input_dir, strategy=strategy)
    except DataError as exc:
        print(f"[LỖI] {exc}")
        return 1

    print(f"Strategy: {strategy}")
    print(f"Thư mục input: {input_dir}")
    print()
    print("Thống kê:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()
    print(f"Mẫu metadata (tối đa 3 / {len(chunks)} chunk hợp lệ):")
    for c in chunks[:3]:
        preview = {k: v for k, v in c.items() if k != "text"}
        preview["text_length"] = len(c["text"])
        print(f"  {preview}")
    return 0


def _cmd_status(strategy: str) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[LỖI CẤU HÌNH] {exc}")
        return 1

    try:
        status = get_status(strategy, config)
    except Exception as exc:  # lỗi Chroma bất ngờ (đĩa, quyền, ...)
        print(f"[LỖI] Không đọc được trạng thái ChromaDB: {exc}")
        return 1

    print("Trạng thái hệ thống (Buổi 07):")
    print(f"  GEMINI_API_KEY: {'Có' if status['api_key_present'] else 'Chưa cấu hình'}")
    print(f"  Embedding model: {status['embedding_model']}")
    print(f"  Embedding dimension: {status['embedding_dim']}")
    print(f"  Strategy: {status['strategy']}")
    print(f"  Collection: {status['collection_name']}")
    print(f"  Collection đã tồn tại: {'Có' if status['collection_exists'] else 'Chưa'}")
    print(f"  Số record đã index: {status['record_count']}")
    if status["collection_exists"]:
        print(f"  Metadata khớp cấu hình hiện tại: {'Có' if status['metadata_ok'] else 'KHÔNG — cần --reset'}")
    return 0


def _cmd_index(strategy: str, reset: bool) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[LỖI CẤU HÌNH] {exc}")
        return 1

    try:
        result = index_chunks(strategy, config, reset=reset)
    except (DataError, EmbeddingError, ChromaError) as exc:
        print(f"[LỖI] {exc}")
        return 1

    print(f"Index thành công cho strategy '{strategy}'.")
    print()
    for k, v in result.items():
        print(f"  {k}: {v}")
    return 0


def _cmd_query(strategy: str, question: str, top_k: int | None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[LỖI CẤU HÌNH] {exc}")
        return 1

    try:
        result = ask(question, strategy, config, top_k=top_k)
    except (DataError, EmbeddingError, ChromaError) as exc:
        print(f"[LỖI] {exc}")
        return 1

    print(f"Status: {result['status']}")
    print(f"Collection: {result['collection']} (strategy={result['strategy']}, top_k={result['top_k']})")
    print()

    if result["answer"]:
        print("Trả lời:")
        print(result["answer"])
        print()

    if result["citations"]:
        print("Citations:")
        for c in result["citations"]:
            print(
                f"  [{c['label']}] {c['source']} (trang {c['page_start']}-{c['page_end']}, "
                f"chunk_id={c['chunk_id']}, distance={c['distance']:.4f})"
            )
        print()

    print(f"Evidence (top {len(result['evidence'])}):")
    for e in result["evidence"]:
        tag = "đạt" if e["accepted"] else "không đạt"
        print(
            f"  {e['label']} [{tag}] distance={e['distance']:.4f} "
            f"{e['source']} (trang {e['page_start']}-{e['page_end']})"
        )

    if result["warnings"]:
        print()
        print("Cảnh báo:")
        for w in result["warnings"]:
            print(f"  - {w}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG Buổi 07")
    subparsers = parser.add_subparsers(dest="command")

    p_validate = subparsers.add_parser("validate", help="Load + validate chunk JSON")
    p_validate.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=VALID_STRATEGIES)

    p_status = subparsers.add_parser("status", help="Xem trạng thái cấu hình + ChromaDB (chỉ đọc)")
    p_status.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=VALID_STRATEGIES)

    p_index = subparsers.add_parser("index", help="Embed + index chunk vào ChromaDB (idempotent)")
    p_index.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=VALID_STRATEGIES)
    p_index.add_argument("--reset", action="store_true", help="Xoá và tạo lại collection đích trước khi index")

    p_query = subparsers.add_parser("query", help="Hỏi đáp qua RAG (retrieval + confidence gate + citation)")
    p_query.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=VALID_STRATEGIES)
    p_query.add_argument("--question", required=True, help="Câu hỏi cần tra cứu")
    p_query.add_argument("--top-k", type=int, default=None, help="Mặc định lấy theo DEFAULT_TOP_K trong .env")

    args = parser.parse_args()

    if args.command == "validate":
        return _cmd_validate(args.strategy)
    if args.command == "status":
        return _cmd_status(args.strategy)
    if args.command == "index":
        return _cmd_index(args.strategy, args.reset)
    if args.command == "query":
        return _cmd_query(args.strategy, args.question, args.top_k)

    print("Lệnh khả dụng hiện tại: validate, status, index, query.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
