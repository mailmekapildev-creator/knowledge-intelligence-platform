"""
Hybrid retrieval: BM25 (lexical) + vector (semantic) search, merged with Reciprocal
Rank Fusion. See docs/retrieval.md for why neither signal alone is sufficient.
"""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.config import settings
from app.db.metadata_store import metadata_store
from app.db.vector_store import vector_store
from app.models.schemas import Chunk, RetrievedChunk
from app.services.embedding.embedder import embed_one


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _bm25_search(tenant_id: str, query: str, top_k: int) -> dict[str, float]:
    chunks = metadata_store.chunks_for_tenant(tenant_id)
    if not chunks:
        return {}
    corpus = [_tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip((c.chunk_id for c in chunks), scores), key=lambda x: x[1], reverse=True)
    return dict(ranked[:top_k])


def _reciprocal_rank_fusion(vector_ranked: list[str], bm25_ranked: list[str], k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for rank, chunk_id in enumerate(vector_ranked):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, chunk_id in enumerate(bm25_ranked):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


def hybrid_search(tenant_id: str, query: str, top_k: int | None = None,
                   metadata_filter: dict | None = None) -> list[RetrievedChunk]:
    top_k = top_k or settings.retrieval_top_k_candidates

    query_vector = embed_one(query)
    vector_hits = vector_store.search(tenant_id, query_vector, top_k, metadata_filter)
    vector_scores = {chunk_id: score for chunk_id, score, _ in vector_hits}

    bm25_scores = _bm25_search(tenant_id, query, top_k)

    vector_ranked = [cid for cid, _, _ in vector_hits]
    bm25_ranked = sorted(bm25_scores, key=lambda cid: bm25_scores[cid], reverse=True)

    fused = _reciprocal_rank_fusion(vector_ranked, bm25_ranked)
    ranked_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:top_k]

    results = []
    for cid in ranked_ids:
        chunk = metadata_store.get_chunk(cid)
        if not chunk:
            continue
        if metadata_filter and not all(chunk.metadata.get(k) == v for k, v in metadata_filter.items()):
            continue
        results.append(RetrievedChunk(
            chunk=chunk,
            vector_score=vector_scores.get(cid, 0.0),
            bm25_score=bm25_scores.get(cid, 0.0),
            fused_score=fused[cid],
        ))
    return results
