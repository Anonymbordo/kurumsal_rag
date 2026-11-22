"""Cümle embedding katmanı.

Varsayılan model çok dilli ve küçük (CPU'da hızlı) bir embedding modelidir; model
dondurulmuş olarak kullanılır, eğitilmez. Model adı GA_EMBED_MODEL ile değişir.

GA_EMBED_MODEL=hashing: indirme gerektirmeyen, karakter n-gram tabanlı yedek
embedder. Testlerde ve internetsiz ilk kurulumda kullanılır; anlamsal kalitesi
gerçek modelin çok altındadır.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from ..config import get_settings


class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray:
        """L2-normalize edilmiş (n, d) matris döndürür; iç çarpım = kosinüs benzerliği."""
        ...


def _normalize(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer  # ağır bağımlılık: gecikmeli yükle

        self.name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        # E5 ailesi girdilerde ön ek bekler; simetrik benzerlik için "query: " önerilir.
        self._prefix = "query: " if "e5" in model_name.lower() else ""

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        vecs = self._model.encode(
            [self._prefix + t for t in texts], normalize_embeddings=True, convert_to_numpy=True, batch_size=32
        )
        return vecs.astype(np.float32)


class HashingEmbedder:
    """Karakter 3–5-gram'larını sabit boyutlu vektöre özetler (indirme yok)."""

    name = "hashing"

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        t = " " + re.sub(r"\s+", " ", text.replace("I", "ı").replace("İ", "i").lower()) + " "
        for n in (3, 4, 5):
            for i in range(len(t) - n + 1):
                h = int.from_bytes(hashlib.blake2b(t[i : i + n].encode(), digest_size=4).digest(), "little")
                v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        return v

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return _normalize(np.stack([self._vec(t) for t in texts]))


@lru_cache
def get_embedder() -> Embedder:
    name = get_settings().embed_model
    if name == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder(name)
