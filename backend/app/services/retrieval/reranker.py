"""
Cross-encoder reranking stage. In production this calls a real cross-encoder model
(e.g., bge-reranker, Cohere Rerank) that jointly encodes (query, chunk) pairs -- far
more precise than bi-encoder cosine similarity alone (see docs/retrieval.md).

The mock scorer below approximates cross-encoder behavior with a lexical-overlap +
length-normalized heuristic so the reranking *stage* (over-fetch -> rerank -> truncate
to top-k) is exercised end to end without requiring a heavyweight model download.
"""
from __future__ import annotations

from app.config import settings
from app.models.schemas import RetrievedChunk


def _mock_cross_encoder_score(query: str, text: str) -> float:
    q_tokens = set(query.lower().split())
    t_tokens = set(text.lower().split())
    if not q_tokens or not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return overlap / (len(q_tokens) ** 0.5)


def rerank(query: str, candidates: list[RetrievedChunk], top_k: int | None = None) -> list[RetrievedChunk]:
    top_k = top_k or settings.rerank_top_k
    scored = []
    for c in candidates:
        score = _mock_cross_encoder_score(query, c.chunk.text)
        c.rerank_score = score
        scored.append(c)
    scored.sort(key=lambda c: c.rerank_score, reverse=True)
    return scored[:top_k]
