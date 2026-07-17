from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from app.core.rate_limiter import rate_limiter
from app.core.security import AuthContext, get_auth_context
from app.models.schemas import Citation, QueryRequest, QueryResponse
from app.services.cache.cache import make_query_cache_key, response_cache
from app.services.llm.gateway import generate
from app.services.llm.prompt_builder import SYSTEM_PROMPT, build_prompt
from app.services.retrieval.hybrid_search import hybrid_search
from app.services.retrieval.reranker import rerank

router = APIRouter(prefix="/api/v1/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest, ctx: AuthContext = Depends(get_auth_context)):
    # Tenant scoping: always from the validated JWT, never trusted from the request body.
    tenant_id = ctx.tenant_id
    if request.tenant_id and request.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id in request does not match authenticated tenant")

    if not rate_limiter.check(tenant_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded, try again shortly")

    start = time.perf_counter()

    cache_key = make_query_cache_key(tenant_id, request.query)
    cached = response_cache.get(cache_key)
    if cached is not None:
        return cached

    candidates = hybrid_search(tenant_id, request.query)
    top_chunks = rerank(request.query, candidates, top_k=request.top_k)

    messages = build_prompt(request.query, top_chunks)
    result = generate(SYSTEM_PROMPT, messages, top_chunks)

    citations = [
        Citation(
            chunk_id=c.chunk.chunk_id,
            document_id=c.chunk.document_id,
            document_title=c.chunk.metadata.get("filename", c.chunk.document_id),
            snippet=c.chunk.text[:200],
        )
        for c in top_chunks
    ]

    response = QueryResponse(
        answer=result.text,
        citations=citations,
        model_used=result.model_used,
        latency_ms=(time.perf_counter() - start) * 1000,
        retrieved_chunk_count=len(top_chunks),
        degraded=result.degraded,
        degraded_reason=result.degraded_reason,
    )

    if not result.degraded:
        response_cache.set(cache_key, response, ttl_seconds=120.0)

    return response
