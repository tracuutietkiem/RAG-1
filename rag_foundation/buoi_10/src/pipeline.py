"""CLI orchestration cho Buổi 10 — nối 5 bước trong SPEC_buoi_10.md mục 2.

Chạy: python -m src.pipeline <parse|embed|load|verify-load> [--input DIR] [--sample N]

Mỗi subcommand độc lập để debug từng khâu (SPEC mục 7), không bắt buộc phải
chạy hết cả pipeline mới thấy kết quả trung gian.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .embedding import (
    EmbeddingConfig,
    SentenceTransformerEmbedder,
    embed_texts,
    warn_long_texts,
)
from .html_parser import Chunk, extract_doc_meta, parse_html_document, print_sample
from .neo4j_loader import (
    INTEGRITY_KEYS,
    DocRelationship,
    DocumentMeta,
    Neo4jConfig,
    default_driver_factory,
    ensure_constraints,
    load_document_chunks,
    load_document_relationships,
    upsert_document,
    verify_load,
)


def _doc_id_from_filename(path: Path) -> str:
    return hashlib.sha1(path.stem.encode("utf-8")).hexdigest()[:12]


def read_document(html_file: Path) -> tuple[DocumentMeta, list[Chunk]]:
    """Đọc một file HTML → (metadata văn bản, danh sách chunk phân cấp).

    doc_id ưu tiên lấy từ <meta name="doc-id"> (số hiệu văn bản thật, ví dụ
    41/2016/TT-NHNN). Chỉ khi HTML không khai báo mới rơi về hash tên file —
    và khi đó in cảnh báo, vì doc_id hash không tra cứu chéo được với các văn
    bản viện dẫn trong `data/doc_relationships.json`.
    """

    raw_html = html_file.read_text(encoding="utf-8")
    meta = extract_doc_meta(raw_html)

    doc_id = meta.get("doc-id")
    if not doc_id:
        doc_id = _doc_id_from_filename(html_file)
        print(
            f"[CẢNH BÁO] {html_file.name} không có <meta name=\"doc-id\">, "
            f"dùng tạm doc_id={doc_id} (không khớp được quan hệ liên văn bản).",
            file=sys.stderr,
        )

    doc = DocumentMeta(
        doc_id=doc_id,
        title=meta.get("title") or html_file.stem,
        doc_type=meta.get("doc-type") or None,
        source_file=html_file.name,
        issue_number=meta.get("issue-number") or None,
    )
    chunks = parse_html_document(doc_id, raw_html)
    return doc, chunks


def _iter_html_files(input_dir: Path):
    files = sorted(input_dir.glob("*.html")) + sorted(input_dir.glob("*.htm"))
    if not files:
        print(
            f"[CẢNH BÁO] Không tìm thấy file .html/.htm nào trong {input_dir}. "
            "Xem SPEC_buoi_10.md mục 4 — cần cung cấp dữ liệu trước khi chạy thật.",
            file=sys.stderr,
        )
    return files


def _print_level_stats(chunks: list[Chunk]) -> None:
    counts: dict[str, int] = {}
    for c in chunks:
        counts[c.level] = counts.get(c.level, 0) + 1
    order = ["chuong", "muc", "dieu", "khoan", "diem", "doan", "bang"]
    parts = [f"{lv}={counts[lv]}" for lv in order if lv in counts]
    warned = sum(1 for c in chunks if c.warnings)
    print(f"    Thống kê cấp bậc: {', '.join(parts)} | chunk có cảnh báo: {warned}")


def _warn_truncation(file_name: str, chunks: list[Chunk], texts: list[str]) -> None:
    """In cảnh báo cho các chunk có nguy cơ bị model cắt ở 512 token.

    Không tự cắt/chia nhỏ — chỉ báo để người dùng biết chunk nào có rủi ro mất
    nội dung khi nhúng (thường là bảng biểu dài).
    """

    risky = warn_long_texts(texts)
    if not risky:
        return
    print(
        f"[CẢNH BÁO] {file_name}: {len(risky)} chunk dài, có thể bị cắt ở 512 token "
        "khi nhúng (vector không phản ánh hết nội dung).",
        file=sys.stderr,
    )
    for i in risky[:5]:
        c = chunks[i]
        print(
            f"    - {c.chunk_id} level={c.level} {len(c.text)} ký tự: {c.text[:60]!r}",
            file=sys.stderr,
        )


def cmd_parse(args: argparse.Namespace) -> None:
    input_dir = Path(args.input)
    for html_file in _iter_html_files(input_dir):
        doc, chunks = read_document(html_file)
        print(f"\n=== {html_file.name} (doc_id={doc.doc_id}) — {len(chunks)} chunk ===")
        _print_level_stats(chunks)
        print_sample(chunks, limit=args.sample)


def cmd_embed(args: argparse.Namespace) -> None:
    load_dotenv()
    input_dir = Path(args.input)
    embedder = SentenceTransformerEmbedder(EmbeddingConfig.from_env())

    for html_file in _iter_html_files(input_dir):
        doc, chunks = read_document(html_file)
        texts = [c.text for c in chunks]
        _warn_truncation(html_file.name, chunks, texts)
        vectors = embed_texts(texts, embedder)
        dim = len(vectors[0]) if vectors else 0
        print(f"{html_file.name}: đã nhúng {len(vectors)} chunk, chiều vector={dim}")


def _load_relationship_file(path: Path) -> tuple[list[dict], list[DocRelationship]]:
    """Đọc data/doc_relationships.json (nếu có). Không có file thì bỏ qua — nhưng
    khi đó đồ thị sẽ KHÔNG có quan hệ liên văn bản nào, verify-load sẽ báo lệch."""

    if not path.exists():
        print(
            f"[CẢNH BÁO] Không thấy {path} — sẽ không nạp quan hệ liên văn bản "
            "(CAN_CU/THAY_THE/HOP_NHAT).",
            file=sys.stderr,
        )
        return [], []

    payload = json.loads(path.read_text(encoding="utf-8"))
    stubs = [d for d in payload.get("documents", []) if not d.get("has_chunks")]
    rels = [
        DocRelationship(r["from"], r["type"], r["to"])
        for r in payload.get("relationships", [])
    ]
    return stubs, rels


def cmd_load(args: argparse.Namespace) -> None:
    load_dotenv()
    input_dir = Path(args.input)
    neo4j_config = Neo4jConfig.from_env()
    embed_config = EmbeddingConfig.from_env()
    embedder = SentenceTransformerEmbedder(embed_config)
    stub_docs, relationships = _load_relationship_file(Path(args.relationships))

    driver = default_driver_factory(neo4j_config)
    try:
        with driver.session(database=neo4j_config.database) as session:
            ensure_constraints(session)

            for html_file in _iter_html_files(input_dir):
                doc, chunks = read_document(html_file)
                texts = [c.text for c in chunks]
                _warn_truncation(html_file.name, chunks, texts)
                vectors = embed_texts(texts, embedder)
                embeddings = {c.chunk_id: v for c, v in zip(chunks, vectors)}
                load_document_chunks(
                    session, doc, chunks, embeddings, embed_config.model_name
                )
                print(f"Đã nạp {html_file.name}: {len(chunks)} chunk")

            # Node stub cho các văn bản được viện dẫn (chưa nạp toàn văn).
            for stub in stub_docs:
                upsert_document(
                    session,
                    DocumentMeta(
                        doc_id=stub["doc_id"],
                        title=stub.get("title") or stub["doc_id"],
                        doc_type=stub.get("doc_type"),
                        source_file=stub.get("source_file") or "",
                        issue_number=stub.get("issue_number"),
                    ),
                )
            if stub_docs:
                print(f"Đã tạo {len(stub_docs)} node Document dạng stub (văn bản viện dẫn)")

            if relationships:
                load_document_relationships(session, relationships)
                print(f"Đã nạp {len(relationships)} quan hệ liên văn bản")
    finally:
        driver.close()


def cmd_verify_load(args: argparse.Namespace) -> None:
    load_dotenv()
    neo4j_config = Neo4jConfig.from_env()
    driver = default_driver_factory(neo4j_config)
    try:
        with driver.session(database=neo4j_config.database) as session:
            result = verify_load(session)
    finally:
        driver.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    report_path = reports_dir / f"verify_{stamp}.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nĐã lưu báo cáo: {report_path}")

    print("\n--- Đối chiếu tiêu chí nghiệm thu ---")
    problems = 0

    expected_docs, expected_rels = 15, 8
    for key, expected in (
        ("document_count", expected_docs),
        ("document_relationship_count", expected_rels),
    ):
        actual = result[key]
        if actual == expected:
            print(f"  [ĐẠT]  {key} = {actual}")
        else:
            problems += 1
            print(f"  [LỆCH] {key} = {actual}, đề bài yêu cầu {expected}")

    for key in INTEGRITY_KEYS:
        actual = result.get(key, 0)
        if actual == 0:
            print(f"  [ĐẠT]  {key} = 0")
        else:
            problems += 1
            print(f"  [LỖI]  {key} = {actual}, phải bằng 0")

    if problems:
        print(
            f"\n{problems} chỉ tiêu chưa đạt. Xem mục 8 trong SPEC_buoi_10.md — "
            "chênh lệch 15/8 là do dữ liệu nguồn thiếu, KHÔNG được thêm node giả "
            "để cho khớp.",
            file=sys.stderr,
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline Buổi 10 (RAG + Neo4j)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Bước 1: chỉ parse + in mẫu, không ghi Neo4j")
    p_parse.add_argument("--input", default="data/raw_html")
    p_parse.add_argument("--sample", type=int, default=10)
    p_parse.set_defaults(func=cmd_parse)

    p_embed = sub.add_parser("embed", help="Bước 1+2: parse + embed, không ghi Neo4j")
    p_embed.add_argument("--input", default="data/raw_html")
    p_embed.set_defaults(func=cmd_embed)

    p_load = sub.add_parser("load", help="Bước 1-4: parse + embed + nạp Neo4j")
    p_load.add_argument("--input", default="data/raw_html")
    p_load.add_argument("--relationships", default="data/doc_relationships.json")
    p_load.set_defaults(func=cmd_load)

    p_verify = sub.add_parser("verify-load", help="Bước 5: xác minh sau khi nạp")
    p_verify.set_defaults(func=cmd_verify_load)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
