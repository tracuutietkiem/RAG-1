"""pipeline.py — CLI chạy luồng OCR + chunking cho Buổi 5.

Cách dùng (chạy từ thư mục buoi_05/):
    python src/pipeline.py                        # dry-run: chỉ in thống kê, KHÔNG ghi file
    python src/pipeline.py --write                 # ghi kết quả thật vào output/
    python src/pipeline.py --pdf ten_file.pdf --write   # chỉ xử lý 1 file cụ thể
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from chunking import fixed_size_chunks, hierarchical_chunks, semantic_chunks
from dotenv import load_dotenv
from ocr_reader import read_pdf

BASE_DIR = Path(__file__).resolve().parent.parent
DATADEMO_DIR = BASE_DIR / "datademo"
OUTPUT_DIR = BASE_DIR / "output"
RAW_DIR = OUTPUT_DIR / "raw"
CHUNKS_DIR = OUTPUT_DIR / "chunks"


def _page_record_to_dict(pr) -> dict:
    return {
        "page": pr.page,
        "text": pr.text,
        "ocr_used": pr.ocr_used,
        "language": pr.language,
    }


def process_pdf(pdf_path: Path, write: bool) -> dict:
    source = pdf_path.name
    stem = pdf_path.stem
    print(f"\n=== Xử lý: {source} ===")

    result = read_pdf(str(pdf_path), source)
    for w in result.global_warnings:
        print(f"[CẢNH BÁO] {w}")

    raw_payload = {
        "source": source,
        "ocr_fallback_triggered": result.ocr_fallback_triggered,
        "pages": [_page_record_to_dict(p) for p in result.pages],
    }

    strategies = {
        "fixed_size": fixed_size_chunks(result.pages, stem),
        "semantic": semantic_chunks(result.pages, stem),
        "hierarchical": hierarchical_chunks(result.pages, stem),
    }

    if write:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{stem}.json").write_text(
            json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for strat_name, chunks in strategies.items():
            (CHUNKS_DIR / f"{stem}_{strat_name}.json").write_text(
                json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(f"Đã ghi: output/raw/{stem}.json và output/chunks/{stem}_<strategy>.json")
    else:
        print("(dry-run — chưa ghi file, thêm --write để ghi thật)")

    return {
        "source": source,
        "ocr_fallback_triggered": result.ocr_fallback_triggered,
        "strategies": strategies,
    }


def _stats_for(chunks: list[dict]) -> str:
    if not chunks:
        return "0 chunk"
    lengths = [len(c["text"]) for c in chunks]
    return (
        f"{len(chunks)} chunk | độ dài min={min(lengths)} "
        f"max={max(lengths)} trung bình={statistics.mean(lengths):.0f}"
    )


def print_summary(all_results: list[dict]) -> None:
    print("\n=== THỐNG KÊ CHUNKING ===")
    for res in all_results:
        print(f"\nFile: {res['source']} (ocr_fallback_triggered={res['ocr_fallback_triggered']})")
        for strat_name, chunks in res["strategies"].items():
            print(f"  - {strat_name:<13}: {_stats_for(chunks)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR + chunking demo cho Buổi 5")
    parser.add_argument("--write", action="store_true", help="Ghi kết quả thật vào output/")
    parser.add_argument("--pdf", type=str, default=None, help="Chỉ xử lý 1 file trong datademo/")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / "src" / ".env")

    if not DATADEMO_DIR.exists():
        print(f"[LỖI] Không tìm thấy thư mục {DATADEMO_DIR}")
        return 1

    if args.pdf:
        pdf_files = [DATADEMO_DIR / args.pdf]
    else:
        pdf_files = sorted(DATADEMO_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"[LỖI] Không có file PDF nào trong {DATADEMO_DIR}")
        return 1

    all_results = []
    for pdf_path in pdf_files:
        if not pdf_path.exists():
            print(f"[LỖI] Không tìm thấy file: {pdf_path}")
            continue
        try:
            all_results.append(process_pdf(pdf_path, write=args.write))
        except Exception as exc:  # noqa: BLE001 - lỗi 1 file không dừng cả job
            print(f"[LỖI] Xử lý {pdf_path.name} thất bại: {exc}")

    print_summary(all_results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
