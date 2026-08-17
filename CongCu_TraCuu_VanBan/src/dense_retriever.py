"""
Dense retrieval.

Hai backend, chon bang DENSE_BACKEND trong .env:

  sentence_transformers  - embedding neural THAT (mac dinh cua project:
                           thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5,
                           giong Buoi 11). Can tai model tu HuggingFace.

  lsa                    - FALLBACK offline: TF-IDF + TruncatedSVD (LSA).
                           Van la vector dense va van bat duoc tuong dong
                           phan phoi tu vung, NHUNG KHONG phai embedding neural.
                           Chi dung khi khong tai duoc model.

  auto (mac dinh)        - thu sentence_transformers, that bai thi tu chuyen
                           sang lsa VA BAO RO trong log/report.

Cache embedding luu trong buoi_14/cache/ (khong ghi ra folder buoi truoc).
"""

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import corpus  # noqa: E402
from src.bm25_retriever import tokenize  # noqa: E402
from src.citation import attach  # noqa: E402


class _Backend:
    name = "?"
    is_neural = False
    detail = ""

    def encode_docs(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def encode_query(self, text: str) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError


class SentenceTransformerBackend(_Backend):
    name = "sentence_transformers"
    is_neural = True

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            config.EMBEDDING_MODEL, device=config.EMBEDDING_DEVICE
        )
        self.detail = f"model={config.EMBEDDING_MODEL}, device={config.EMBEDDING_DEVICE}"

    def encode_docs(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(texts, batch_size=16, show_progress_bar=False,
                              normalize_embeddings=True),
            dtype="float32",
        )

    def encode_query(self, text: str) -> np.ndarray:
        return np.asarray(
            self.model.encode([text], normalize_embeddings=True), dtype="float32"
        )[0]


class LSABackend(_Backend):
    name = "lsa"
    is_neural = False

    def __init__(self, dim: int = None) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.dim = dim or config.LSA_DIM
        self.vectorizer = TfidfVectorizer(
            analyzer=tokenize, min_df=1, sublinear_tf=True
        )
        self.svd = TruncatedSVD(n_components=self.dim, random_state=42)
        self.detail = f"TF-IDF + TruncatedSVD(dim={self.dim}) - FALLBACK, khong phai neural"

    def encode_docs(self, texts: list[str]) -> np.ndarray:
        X = self.vectorizer.fit_transform(texts)
        n_comp = min(self.dim, X.shape[1] - 1, X.shape[0] - 1)
        if n_comp != self.dim:
            self.svd.set_params(n_components=n_comp)
            self.dim = n_comp
            self.detail = f"TF-IDF + TruncatedSVD(dim={n_comp}) - FALLBACK, khong phai neural"
        V = self.svd.fit_transform(X).astype("float32")
        return _l2(V)

    def encode_query(self, text: str) -> np.ndarray:
        X = self.vectorizer.transform([text])
        V = self.svd.transform(X).astype("float32")
        return _l2(V)[0]


def _l2(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def _make_backend() -> _Backend:
    want = config.DENSE_BACKEND
    if want == "lsa":
        return LSABackend()
    if want in ("sentence_transformers", "auto"):
        try:
            return SentenceTransformerBackend()
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {str(exc)[:200]}"
            if want == "sentence_transformers":
                raise RuntimeError(
                    f"Khong khoi tao duoc sentence-transformers ({msg}). "
                    f"Dat DENSE_BACKEND=lsa neu muon chay offline."
                ) from exc
            print(
                "[CANH BAO] Khong dung duoc sentence-transformers "
                f"({msg}).\n"
                "           -> Chuyen sang FALLBACK 'lsa' (TF-IDF+SVD). "
                "Day KHONG phai neural embedding.",
                file=sys.stderr,
            )
            b = LSABackend()
            b.detail += f" | ly do fallback: {msg}"
            return b
    raise ValueError(f"DENSE_BACKEND khong hop le: {want}")


class DenseRetriever:
    method = "dense"

    def __init__(self) -> None:
        self.records = list(corpus.load_chunks())
        self.backend = _make_backend()
        texts = [corpus.index_text_of(r) for r in self.records]

        cache_file = (
            config.CACHE_DIR
            / f"emb_{self.backend.name}_{corpus.corpus_fingerprint()}.npy"
        )
        if self.backend.name == "sentence_transformers" and cache_file.exists():
            self.matrix = np.load(cache_file)
            self.from_cache = True
        else:
            self.matrix = self.backend.encode_docs(texts)
            self.from_cache = False
            if self.backend.name == "sentence_transformers":
                np.save(cache_file, self.matrix)
        self.cache_file = cache_file

    @property
    def backend_name(self) -> str:
        return self.backend.name

    @property
    def is_neural(self) -> bool:
        return self.backend.is_neural

    @property
    def backend_detail(self) -> str:
        return self.backend.detail

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        q = self.backend.encode_query(question)
        scores = self.matrix @ q
        order = np.argsort(-scores)[:top_k]
        results = []
        for rank, idx in enumerate(order, start=1):
            results.append(
                attach(
                    self.records[int(idx)],
                    rank=rank,
                    retrieval_score=round(float(scores[int(idx)]), 6),
                    retrieval_method=self.method,
                )
            )
        return results


@lru_cache(maxsize=1)
def get_retriever() -> DenseRetriever:
    return DenseRetriever()
