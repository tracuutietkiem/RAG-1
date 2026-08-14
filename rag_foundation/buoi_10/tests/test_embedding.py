import unittest

from src.embedding import EmbeddingConfig, embed_texts


class FakeEmbedder:
    """Fake embed_fn: vector cố định chiều 8, deterministic theo độ dài text.
    Không tải model thật, không cần torch cài sẵn để chạy test này."""

    def __call__(self, texts):
        return [[float(len(t))] * 8 for t in texts]


class EmbedTextsTests(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        self.assertEqual(embed_texts([], FakeEmbedder()), [])

    def test_returns_one_vector_per_text(self):
        texts = ["a", "bb", "ccc"]
        vectors = embed_texts(texts, FakeEmbedder())
        self.assertEqual(len(vectors), 3)
        self.assertEqual(len(vectors[0]), 8)

    def test_mismatched_embed_fn_raises(self):
        bad_fn = lambda texts: [[0.0]]  # luôn trả 1 vector bất kể input
        with self.assertRaises(ValueError):
            embed_texts(["a", "b"], bad_fn)


class EmbeddingConfigTests(unittest.TestCase):
    def test_from_env_rejects_non_cpu_device(self):
        import os

        os.environ["EMBEDDING_DEVICE"] = "cuda"
        try:
            with self.assertRaises(ValueError):
                EmbeddingConfig.from_env()
        finally:
            del os.environ["EMBEDDING_DEVICE"]

    def test_from_env_defaults_to_cpu(self):
        import os

        os.environ.pop("EMBEDDING_DEVICE", None)
        config = EmbeddingConfig.from_env()
        self.assertEqual(config.device, "cpu")


if __name__ == "__main__":
    unittest.main()
