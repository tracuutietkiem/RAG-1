"""
BM25 / lexical retrieval.

Tokenizer duoc thiet ke de GIU:
  - ma van ban: 01/2014/TT-NHNN, 32/2024/QH15, 17/VBHN-BTC
  - so dieu:    "Điều 12" -> token "điều" + "12" + token ghep "điều_12"
  - tu tieng Viet co dau (NFC)
"""

import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import corpus  # noqa: E402
from src.citation import attach  # noqa: E402

# Token: cum chu/so, cho phep '/' va '-' o GIUA (de giu ma van ban)
RE_TOKEN = re.compile(r"[0-9a-zA-ZÀ-ỹ]+(?:[/\-][0-9a-zA-ZÀ-ỹ]+)*")
RE_ARTICLE_REF = re.compile(r"điều\s+(\d+[a-zà-ỹ]?)")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []

    # Giu cum "dieu <so>" thanh mot token ghep -> tin hieu manh cho cau hoi ve so dieu
    for m in RE_ARTICLE_REF.finditer(text):
        tokens.append(f"điều_{m.group(1)}")

    for m in RE_TOKEN.finditer(text):
        tok = m.group(0)
        tokens.append(tok)
        # Ma van ban: bo sung cac manh de van khop khi nguoi dung go thieu
        if "/" in tok or "-" in tok:
            for part in re.split(r"[/\-]", tok):
                if len(part) >= 2:
                    tokens.append(part)
    return tokens


class BM25Retriever:
    """BM25Okapi tren corpus da chuan hoa."""

    method = "bm25"

    def __init__(self) -> None:
        from rank_bm25 import BM25Okapi

        self.records = list(corpus.load_chunks())
        self.corpus_tokens = [tokenize(corpus.index_text_of(r)) for r in self.records]
        self.bm25 = BM25Okapi(self.corpus_tokens)

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        q_tokens = tokenize(question)
        if not q_tokens:
            return []
        scores = self.bm25.get_scores(q_tokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for rank, idx in enumerate(order[:top_k], start=1):
            if scores[idx] <= 0:
                continue
            results.append(
                attach(
                    self.records[idx],
                    rank=rank,
                    retrieval_score=round(float(scores[idx]), 6),
                    retrieval_method=self.method,
                )
            )
        return results


@lru_cache(maxsize=1)
def get_retriever() -> BM25Retriever:
    return BM25Retriever()
