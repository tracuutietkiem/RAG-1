"""CLI orchestration cho Buổi 11 — nối các bước trong SPEC_buoi_11.md mục 2.

Chạy: python -m src.pipeline <setup-index|ask|compare> [tham số]

Mỗi subcommand độc lập để debug từng khâu, không bắt buộc phải chạy hết cả
pipeline mới thấy kết quả trung gian (cùng phong cách Buổi 10).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .embedding import EmbeddingConfig, SentenceTransformerEmbedder, embed_query
from .gemini_qa import NO_CONTEXT_ANSWER_HINT, GeminiClient, GeminiConfig, answer_question
from .graph_search import (
    ContextChunk,
    Neo4jConfig,
    SearchConfig,
    create_vector_index,
    default_driver_factory,
    has_vector_index,
    search_context,
)

#: 5 câu hỏi kiểm thử đúng nguyên văn đề bài (buoi_11.md mục "Bước 4").
TEST_QUESTIONS = [
    "Nghị định 46/2023/NĐ-CP thay thế cho nghị định nào, và nghị định bị thay "
    "thế đó có nội dung gì nổi bật về kinh doanh bảo hiểm?",
    "Văn bản hợp nhất số 52/VBHN-NHNN được hợp nhất từ văn bản nào, và quy "
    "định về hồ sơ, thủ tục cấp giấy phép lần đầu của ngân hàng thương mại "
    "gồm những tài liệu gì?",
    "Thông tư số 01/2025/TT-NHNN quy định về cấp giấy phép quỹ tín dụng nhân "
    "dân được sửa đổi, bổ sung bởi văn bản nào, và những nội dung sửa đổi bổ "
    "sung chính là gì?",
    "Thông tư số 41/2016/TT-NHNN về tỷ lệ an toàn vốn của ngân hàng căn cứ "
    "vào luật nào, và luật đó quy định chức năng nhiệm vụ của cơ quan nào?",
    "Hoạt động giao nhận, vận chuyển tiền mặt và tài sản quý của Ngân hàng "
    "Nhà nước được điều chỉnh bởi Thông tư nào, và Thông tư đó có được sửa "
    "đổi bổ sung bởi văn bản nào không?",
]

#: Các mức bước nhảy dùng để so sánh ở subcommand `compare` (đề bài yêu cầu
#: đúng 3 mức 0/1/2, xem buoi_11.md mục "Bước 4").
COMPARE_HOPS = (0, 1, 2)


def _require_vector_index(session) -> None:
    if not has_vector_index(session):
        print(
            "[LỖI] Chưa có vector index 'chunk_embedding_index' trong database. "
            "Chạy `python -m src.pipeline setup-index` trước (SPEC mục 4).",
            file=sys.stderr,
        )
        raise SystemExit(1)


def cmd_setup_index(args: argparse.Namespace) -> None:
    load_dotenv()
    neo4j_config = Neo4jConfig.from_env()
    driver = default_driver_factory(neo4j_config)
    try:
        with driver.session(database=neo4j_config.database) as session:
            if has_vector_index(session):
                print("Vector index đã tồn tại, không cần tạo lại.")
                return
            create_vector_index(session)
            print("Đã tạo vector index 'chunk_embedding_index' (384 chiều, cosine).")
    finally:
        driver.close()


def _format_sources(chunks: list[ContextChunk]) -> str:
    if not chunks:
        return "  (không có nguồn nào được truy hồi)"
    lines = []
    for c in chunks:
        heading = c.heading or f"(cấp {c.level})"
        lines.append(
            f"  - hop={c.hop} score={c.score:.4f} doc_id={c.doc_id} {heading} "
            f"[{c.chunk_id}]"
        )
    return "\n".join(lines)


def _run_one_question(
    session, embedder, gemini_call_fn, question: str, hops: int, top_k_direct: int, top_k_per_hop: int
) -> tuple[list[ContextChunk], str]:
    query_vector = embed_query(question, embedder)
    search_config = SearchConfig(top_k_direct=top_k_direct, top_k_per_hop=top_k_per_hop, hops=hops)
    chunks = search_context(session, query_vector, search_config)
    answer = answer_question(question, chunks, gemini_call_fn)
    return chunks, answer


def cmd_ask(args: argparse.Namespace) -> None:
    load_dotenv()
    neo4j_config = Neo4jConfig.from_env()
    embedder = SentenceTransformerEmbedder(EmbeddingConfig.from_env())
    gemini_client = GeminiClient(GeminiConfig.from_env())

    driver = default_driver_factory(neo4j_config)
    try:
        with driver.session(database=neo4j_config.database) as session:
            _require_vector_index(session)
            chunks, answer = _run_one_question(
                session, embedder, gemini_client, args.question, args.hops,
                args.top_k_direct, args.top_k_per_hop,
            )
    finally:
        driver.close()

    print(f"\n=== Câu hỏi (hops={args.hops}) ===\n{args.question}\n")
    print(f"=== Trả lời ===\n{answer}\n")
    print(f"=== Nguồn ({len(chunks)} chunk) ===\n{_format_sources(chunks)}")


def cmd_compare(args: argparse.Namespace) -> None:
    load_dotenv()
    neo4j_config = Neo4jConfig.from_env()
    embedder = SentenceTransformerEmbedder(EmbeddingConfig.from_env())
    gemini_client = GeminiClient(GeminiConfig.from_env())

    driver = default_driver_factory(neo4j_config)
    report_lines: list[str] = []
    report_lines.append("# So sánh Q&A theo số bước nhảy (Multi-hop) — Buổi 11")
    report_lines.append("")
    report_lines.append(
        f"Sinh tự động lúc {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} bằng "
        "`python -m src.pipeline compare`. Xem SPEC_buoi_11.md mục 6 về giới hạn "
        "dữ liệu thật (đồ thị hiện chỉ có 4 Document, 3 quan hệ CAN_CU)."
    )
    report_lines.append("")

    try:
        with driver.session(database=neo4j_config.database) as session:
            _require_vector_index(session)
            for i, question in enumerate(TEST_QUESTIONS, start=1):
                print(f"[{i}/{len(TEST_QUESTIONS)}] {question}", file=sys.stderr)
                report_lines.append(f"## Câu hỏi {i}")
                report_lines.append("")
                report_lines.append(f"> {question}")
                report_lines.append("")
                for hops in COMPARE_HOPS:
                    chunks, answer = _run_one_question(
                        session, embedder, gemini_client, question, hops,
                        args.top_k_direct, args.top_k_per_hop,
                    )
                    report_lines.append(f"### hops = {hops} ({len(chunks)} chunk ngữ cảnh)")
                    report_lines.append("")
                    report_lines.append("**Trả lời:**")
                    report_lines.append("")
                    report_lines.append(answer.strip() or "(rỗng)")
                    report_lines.append("")
                    report_lines.append("**Nguồn:**")
                    report_lines.append("")
                    report_lines.append("```")
                    report_lines.append(_format_sources(chunks))
                    report_lines.append("```")
                    report_lines.append("")
    finally:
        driver.close()

    report_lines.append("---")
    report_lines.append("")
    report_lines.append(
        "**Ghi chú đánh giá:** so sánh thủ công câu trả lời giữa các mức hops ở "
        "trên. Với dữ liệu hiện tại (chỉ 1 văn bản toàn văn + 3 stub CAN_CU), kỳ "
        "vọng chỉ Câu hỏi 4 có ngữ cảnh đầy đủ; 4 câu còn lại nên trả lời "
        f'"{NO_CONTEXT_ANSWER_HINT}" '
        "ở mọi mức hops vì văn bản được hỏi tới không có trong đồ thị — đây là "
        "kết quả ĐÚNG, không phải lỗi (SPEC mục 6)."
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nĐã ghi báo cáo: {out_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline Buổi 11 (Multi-hop Graph RAG + Gemini QA)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser("setup-index", help="Tạo vector index trên (:Chunk).embedding")
    p_setup.set_defaults(func=cmd_setup_index)

    p_ask = sub.add_parser("ask", help="Hỏi 1 câu, chọn số bước nhảy tuỳ ý")
    p_ask.add_argument("question", help="Câu hỏi (bọc trong dấu ngoặc kép)")
    p_ask.add_argument("--hops", type=int, default=0, help="Số bước nhảy multi-hop (mặc định 0)")
    p_ask.add_argument("--top-k-direct", type=int, default=5, dest="top_k_direct")
    p_ask.add_argument("--top-k-per-hop", type=int, default=2, dest="top_k_per_hop")
    p_ask.set_defaults(func=cmd_ask)

    p_compare = sub.add_parser(
        "compare", help="Chạy 5 câu hỏi mẫu ở hops=0,1,2, ghi reports/qa_comparison.md"
    )
    p_compare.add_argument("--output", default="reports/qa_comparison.md")
    p_compare.add_argument("--top-k-direct", type=int, default=5, dest="top_k_direct")
    p_compare.add_argument("--top-k-per-hop", type=int, default=2, dest="top_k_per_hop")
    p_compare.set_defaults(func=cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
