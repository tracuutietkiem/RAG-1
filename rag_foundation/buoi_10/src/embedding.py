"""Bước 2 (SPEC_buoi_10.md mục 2, 6): nhúng vector cho các chunk văn bản.

Model mặc định: thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5 (HuggingFace),
chạy bắt buộc trên CPU theo yêu cầu đề bài (máy học viên không có GPU).

`embed_fn` luôn injectable để test không phải tải model thật (xem
tests/test_embedding.py) — đúng phong cách dependency injection của các buổi
trước (SPEC_buoi_09.md mục 12).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Sequence

EmbedFn = Callable[[Sequence[str]], list[list[float]]]

DEFAULT_MODEL_NAME = "thuannc/vi-distilled-msmarco-MiniLM-L12-cos-v5"


@dataclass
class EmbeddingConfig:
    model_name: str = DEFAULT_MODEL_NAME
    device: str = "cpu"
    batch_size: int = 16

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        if device != "cpu":
            # Đề bài yêu cầu rõ: chỉ cài/dùng bản CPU (pytorch-cpu). Không âm thầm
            # chuyển sang cuda nếu ai đó chỉnh nhầm biến môi trường.
            raise ValueError(
                "EMBEDDING_DEVICE phải là 'cpu' theo yêu cầu đề bài Buổi 10 "
                f"(nhận được: {device!r})"
            )
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME),
            device=device,
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "16")),
        )


class SentenceTransformerEmbedder:
    """Bọc sentence-transformers, chỉ import thư viện nặng khi thực sự cần
    (lazy import) để test/parse-only không bắt buộc cài torch."""

    def __init__(self, config: EmbeddingConfig | None = None):
        self.config = config or EmbeddingConfig.from_env()
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy import

            self._model = SentenceTransformer(
                self.config.model_name, device=self.config.device
            )
        return self._model

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(
            list(texts),
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]


#

# Model có max_seq_length = 512 token (xác nhận từ model card trên HuggingFace:
# Pooling word_embedding_dimension = 384, Transformer max_seq_length = 512).
# Văn bản dài hơn sẽ bị CẮT ÂM THẦM bởi sentence-transformers — với văn bản pháp
# luật, phần bị cắt có thể là chính nội dung cần tra cứu. Vì vậy phải cảnh báo.
MAX_SEQ_TOKENS = 512
# Tiếng Việt trung bình ~3 ký tự/token với tokenizer của model này (ước lượng
# thận trọng, không phải con số chính xác — chỉ dùng để cảnh báo sớm).
CHARS_PER_TOKEN_ESTIMATE = 3


def warn_long_texts(texts: Sequence[str]) -> list[int]:
    """Trả về index các văn bản có nguy cơ bị cắt khi nhúng. Caller nên in cảnh báo.

    Không tự động cắt, không tự động chia nhỏ — quyết định đó thuộc về người
    thiết kế pipeline, không nên xảy ra ngầm bên trong hàm nhúng.
    """

    limit_chars = MAX_SEQ_TOKENS * CHARS_PER_TOKEN_ESTIMATE
    return [i for i, t in enumerate(texts) if len(t) > limit_chars]


def embed_texts(texts: Sequence[str], embed_fn: EmbedFn) -> list[list[float]]:
    """Hàm mỏng, thuần: nhận embed_fn injectable, không tự quyết định model.

    Không gọi trực tiếp SentenceTransformerEmbedder ở đây để pipeline.py và test
    có thể tiêm fake embed_fn mà không phải mock nội bộ module.
    """

    if not texts:
        return []
    vectors = embed_fn(texts)
    if len(vectors) != len(texts):
        raise ValueError(
            f"embed_fn trả về {len(vectors)} vector cho {len(texts)} văn bản đầu vào"
        )
    return vectors
