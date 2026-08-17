"""
Reranking - tang xep hang lai SAU Hybrid Search.

Reranker KHONG thay the Hybrid Search. No chi nhan candidate tu Hybrid
(candidate_k) roi cham diem lai tung cap (question, candidate) va chon top_k.
Khong bao gio chay tren toan corpus.

Hai backend, chon bang RERANKER_BACKEND:

  cross_encoder - Cross-Encoder THAT (mac dinh project: BAAI/bge-reranker-v2-m3,
                  giong Buoi 09). Can tai model tu HuggingFace (~2,27 GB).

  fallback      - KHONG phai neural reranker. Cham diem lai bang do phu tu vung
                  co trong so IDF + thuong cho cum tu khop nguyen van + thuong
                  cho ma van ban/so dieu trung khop. Day la mot ham cham diem
                  DOC LAP voi RRF (khong phai sort lai hybrid_score), nhung phai
                  duoc bao cao ro rang la FALLBACK.

  auto          - thu cross_encoder, that bai thi fallback VA bao ro.
"""

import math
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import corpus  # noqa: E402
from src.bm25_retriever import tokenize  # noqa: E402

RE_DOC_CODE = re.compile(r"\d+/\d{4}/[A-Za-zĐ\-]+", re.IGNORECASE)
RE_ARTICLE = re.compile(r"điều\s+\d+[a-zà-ỹ]?", re.IGNORECASE)


class _Base:
    name = "?"
    is_neural = False
    detail = ""

    def score(self, question: str, texts: list[str]) -> list[float]:  # pragma: no cover
        raise NotImplementedError


class CrossEncoderBackend(_Base):
    name = "cross_encoder"
    is_neural = True

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(
            config.RERANKER_MODEL,
            max_length=config.RERANKER_MAX_LENGTH,
            device=config.RERANK_DEVICE,
        )
        self.detail = (
            f"model={config.RERANKER_MODEL}, max_length={config.RERANKER_MAX_LENGTH}, "
            f"device={config.RERANK_DEVICE}"
        )

    def score(self, question: str, texts: list[str]) -> list[float]:
        pairs = [(question, t) for t in texts]
        raw = self.model.predict(pairs, batch_size=config.RERANK_BATCH_SIZE)
        return [float(x) for x in raw]


class LexicalFallbackBackend(_Base):
    name = "fallback_lexical_overlap"
    is_neural = False

    def __init__(self) -> None:
        records = corpus.load_chunks()
        n_docs = len(records)
        df: Counter = Counter()
        for r in records:
            for tok in set(tokenize(corpus.index_text_of(r))):
                df[tok] += 1
        self.idf = {
            tok: math.log(1.0 + (n_docs - c + 0.5) / (c + 0.5)) for tok, c in df.items()
        }
        self.default_idf = math.log(1.0 + (n_docs + 0.5) / 0.5)
        self.detail = (
            "FALLBACK - IDF-weighted token coverage + phrase bonus + "
            "document-code/article bonus (KHONG phai neural cross-encoder)"
        )

    def score(self, question: str, texts: list[str]) -> list[float]:
        q_tokens = tokenize(question)
        if not q_tokens:
            return [0.0] * len(texts)
        q_set = set(q_tokens)
        q_weight = sum(self.idf.get(t, self.default_idf) for t in q_set) or 1.0

        q_low = question.lower()
        q_codes = {c.lower() for c in RE_DOC_CODE.findall(question)}
        q_arts = {a.lower() for a in RE_ARTICLE.findall(question)}
        # cum 3 tu lien tiep de thuong cho khop nguyen van
        words = [w for w in re.split(r"\W+", q_low) if w]
        q_phrases = {" ".join(words[i:i + 3]) for i in range(max(0, len(words) - 2))}

        out = []
        for text in texts:
            t_low = text.lower()
            t_set = set(tokenize(text))
            covered = q_set & t_set
            coverage = sum(self.idf.get(t, self.default_idf) for t in covered) / q_weight

            phrase_bonus = 0.0
            if q_phrases:
                hit = sum(1 for p in q_phrases if p and p in t_low)
                phrase_bonus = 0.30 * (hit / len(q_phrases))

            code_bonus = 0.25 if q_codes and any(c in t_low for c in q_codes) else 0.0
            art_bonus = 0.20 if q_arts and any(a in t_low for a in q_arts) else 0.0

            # phat nhe voi doan qua dai (loang thong tin)
            length_penalty = 1.0 / (1.0 + max(0, len(text) - 2500) / 5000.0)

            out.append(
                round((coverage + phrase_bonus + code_bonus + art_bonus) * length_penalty, 6)
            )
        return out


def _make_backend() -> _Base:
    want = config.RERANKER_BACKEND
    if want == "fallback":
        return LexicalFallbackBackend()
    if want in ("cross_encoder", "auto"):
        try:
            return CrossEncoderBackend()
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {str(exc)[:200]}"
            if want == "cross_encoder":
                raise RuntimeError(
                    f"Khong khoi tao duoc Cross-Encoder ({msg}). "
                    f"Dat RERANKER_BACKEND=fallback neu muon chay offline."
                ) from exc
            print(
                f"[CANH BAO] Khong dung duoc Cross-Encoder ({msg}).\n"
                "           -> Chuyen sang FALLBACK lexical. "
                "DAY KHONG PHAI NEURAL RERANKER.",
                file=sys.stderr,
            )
            b = LexicalFallbackBackend()
            b.detail += f" | ly do fallback: {msg}"
            return b
    raise ValueError(f"RERANKER_BACKEND khong hop le: {want}")


class Reranker:
    def __init__(self) -> None:
        self.backend = _make_backend()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    @property
    def is_neural(self) -> bool:
        return self.backend.is_neural

    @property
    def backend_detail(self) -> str:
        return self.backend.detail

    def rerank(self, question: str, candidates: list[dict], top_k: int = None) -> list[dict]:
        """candidates PHAI la output cua Hybrid Search, khong phai toan corpus."""
        top_k = top_k or config.FINAL_TOP_K
        if not candidates:
            return []
        scores = self.backend.score(
            question, [c.get("index_text") or c["text"] for c in candidates]
        )

        merged = []
        for cand, sc in zip(candidates, scores):
            item = dict(cand)
            item["hybrid_rank"] = cand.get("final_rank", cand.get("rank"))
            item["hybrid_score"] = cand.get("rrf_score", cand.get("retrieval_score"))
            item["rerank_score"] = round(float(sc), 6)
            item["retrieval_method"] = "hybrid_rerank"
            merged.append(item)

        merged.sort(key=lambda x: (-x["rerank_score"], x["hybrid_rank"] or 10**9))
        for i, item in enumerate(merged, start=1):
            item["final_rank"] = i
            item["rank"] = i
            item["retrieval_score"] = item["rerank_score"]
        return merged[:top_k]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return Reranker()
