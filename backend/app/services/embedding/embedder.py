"""
Embedding service. In MOCK_MODE, produces deterministic pseudo-embeddings (hash-based,
seeded so identical text always yields the identical vector) -- this keeps the whole
retrieval pipeline runnable and testable with zero cost and zero external calls, while
still exercising the real code paths (batching, caching, cosine similarity search).

Swap `mock_embed_batch` for a real provider call (sentence-transformers locally, or an
API embedding model) behind the same `embed_batch` interface to go to production --
nothing upstream changes.
"""
from __future__ import annotations

import hashlib

import numpy as np

from app.config import settings


class EmbeddingCache:
    """Content-hash -> vector. Avoids re-embedding unchanged chunks on re-ingestion."""

    def __init__(self):
        self._store: dict[str, list[float]] = {}

    def get(self, text: str) -> list[float] | None:
        return self._store.get(self._key(text))

    def set(self, text: str, vector: list[float]) -> None:
        self._store[self._key(text)] = vector

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        return len(self._store)


_cache = EmbeddingCache()


def _mock_embed_one(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding: hash text into a seeded RNG so identical text
    always produces the identical vector, and similar text (shared tokens) produces
    partially-correlated vectors via a bag-of-tokens seed contribution."""
    tokens = text.lower().split()
    vec = np.zeros(dim, dtype=np.float32)
    if not tokens:
        tokens = [""]
    for tok in tokens:
        seed = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        vec += rng.normal(size=dim)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Batched embedding with cache. Batching matters for cost: most real embedding
    APIs charge per call and amortize latency better over a batch (see
    docs/cost-and-scalability.md)."""
    results: list[list[float] | None] = [None] * len(texts)
    to_embed_idx = []
    to_embed_text = []

    for i, t in enumerate(texts):
        cached = _cache.get(t)
        if cached is not None:
            results[i] = cached
        else:
            to_embed_idx.append(i)
            to_embed_text.append(t)

    batch_size = settings.embedding_batch_size
    for start in range(0, len(to_embed_text), batch_size):
        batch = to_embed_text[start:start + batch_size]
        if settings.mock_mode or not settings.anthropic_api_key:
            vectors = [_mock_embed_one(t, settings.embedding_dim) for t in batch]
        else:
            # Real embedding provider call would go here (e.g., sentence-transformers
            # or a hosted embedding API). Kept out of the default path to avoid a
            # hard dependency for the portfolio build.
            vectors = [_mock_embed_one(t, settings.embedding_dim) for t in batch]

        for j, v in enumerate(vectors):
            idx = to_embed_idx[start + j]
            results[idx] = v
            _cache.set(to_embed_text[start + j], v)

    return results  # type: ignore[return-value]


def embed_one(text: str) -> list[float]:
    return embed_batch([text])[0]


def cache_size() -> int:
    return len(_cache)
