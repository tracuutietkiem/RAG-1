"""
Hybrid Search bang Reciprocal Rank Fusion (RRF).

Vi sao RRF:
  - khong can ep BM25 score va cosine score ve cung mot thang do;
  - chi dung THU HANG, nen mien nhiem voi viec hai retriever co thang diem khac han nhau;
  - de giai thich cho hoc vien.

    rrf(d) = sum_over_retrievers( weight / (K + rank_of_d_in_that_retriever) )

Candidate chi xuat hien o MOT retriever van duoc giu (dung nghiep vu: BM25 bat ma
van ban ma Dense bo sot, va nguoc lai).
"""

import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import bm25_retriever, corpus, dense_retriever  # noqa: E402
from src.citation import attach  # noqa: E402


class HybridRetriever:
    method = "hybrid"

    def __init__(self) -> None:
        self.bm25 = bm25_retriever.get_retriever()
        self.dense = dense_retriever.get_retriever()
        self.index = corpus.chunk_index()

    @property
    def dense_backend(self) -> str:
        return self.dense.backend_name

    def search(
        self,
        question: str,
        top_k: int = None,
        candidate_k: int = None,
    ) -> list[dict]:
        top_k = top_k or config.FINAL_TOP_K
        candidate_k = candidate_k or config.CANDIDATE_K

        bm_hits = self.bm25.search(question, candidate_k)
        dn_hits = self.dense.search(question, candidate_k)

        bm_rank = {h["chunk_id"]: h["rank"] for h in bm_hits}
        dn_rank = {h["chunk_id"]: h["rank"] for h in dn_hits}
        bm_score = {h["chunk_id"]: h["retrieval_score"] for h in bm_hits}
        dn_score = {h["chunk_id"]: h["retrieval_score"] for h in dn_hits}

        fused: dict[str, float] = {}
        for cid, rank in bm_rank.items():
            fused[cid] = fused.get(cid, 0.0) + config.RRF_BM25_WEIGHT / (config.RRF_K + rank)
        for cid, rank in dn_rank.items():
            fused[cid] = fused.get(cid, 0.0) + config.RRF_DENSE_WEIGHT / (config.RRF_K + rank)

        ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))

        results = []
        for final_rank, (cid, score) in enumerate(ordered[:top_k], start=1):
            rec = self.index.get(cid)
            if rec is None:
                continue
            results.append(
                attach(
                    rec,
                    final_rank=final_rank,
                    rank=final_rank,
                    bm25_rank=bm_rank.get(cid),
                    dense_rank=dn_rank.get(cid),
                    bm25_score=bm_score.get(cid),
                    dense_score=dn_score.get(cid),
                    rrf_score=round(score, 8),
                    retrieval_score=round(score, 8),
                    retrieval_method=self.method,
                )
            )
        return results

    def candidates(self, question: str, candidate_k: int = None) -> list[dict]:
        """Tra ve day du candidate (dung lam dau vao cho reranker)."""
        candidate_k = candidate_k or config.CANDIDATE_K
        return self.search(question, top_k=candidate_k, candidate_k=candidate_k)


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    return HybridRetriever()
