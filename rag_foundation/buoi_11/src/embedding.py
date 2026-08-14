"""Nhúng vector cho câu hỏi người dùng — PHẢI dùng cùng model, cùng chiều
(384) với Buổi 10 để vector câu hỏi và vector chunk nằm chung không gian.

Bản sao rút gọn từ `buoi_10/src/embedding.py` (chỉ đọc tham chiếu, không
import chéo thư mục — mỗi buổi tự chứa, xem SPEC_buoi_11.md mục 1). Giữ
nguyên default model, `device=cpu` bắt buộc, và cơ chế `embed_fn` injectable
để test offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Sequence

EmbedFn = Callable[[Sequence[str]], list[list[float]]]

DEFAULT_MODEL_NAME = "thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5"
EMBEDDING_DIM = 384


@dataclass
class EmbeddingConfig:
    model_name: str = DEFAULT_MODEL_NAME
    device: str = "cpu"

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        if device != "cpu":
            raise ValueError(
                "EMBEDDING_DEVICE phải là 'cpu' (giống Buổi 10), "
                f"nhận được: {device!r}"
            )
        return cls(model_name=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME), device=device)


class SentenceTransformerEmbedder:
    """Lazy-load sentence-transformers — test/parse-only không bắt buộc cài torch."""

    def __init__(self, config: EmbeddingConfig | None = None):
        self.config = config or EmbeddingConfig.from_env()
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy import

            self._model = SentenceTransformer(self.config.model_name, device=self.config.device)
        return self._model

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(list(texts), show_progress_bar=False, convert_to_numpy=True)
        return [v.tolist() for v in vectors]


def embed_query(text: str, embed_fn: EmbedFn) -> list[float]:
    """Nhúng một câu hỏi thành một vector. Hàm mỏng, thuần — embed_fn injectable
    để test không cần tải model thật."""

    vectors = embed_fn([text])
    if len(vectors) != 1:
        raise ValueError(f"embed_fn phải trả về đúng 1 vector cho 1 câu hỏi, nhận {len(vectors)}")
    return vectors[0]
