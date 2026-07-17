from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.security import AuthContext, Role, get_auth_context, mint_dev_token, require_role
from app.db.metadata_store import metadata_store
from app.db.vector_store import vector_store
from app.services.cache.cache import response_cache, retrieval_cache
from app.services.embedding.embedder import cache_size

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def stats(ctx: AuthContext = Depends(get_auth_context)):
    checked = require_role(Role.tenant_admin)(ctx)
    docs = metadata_store.list_documents(checked.tenant_id)
    return {
        "tenant_id": checked.tenant_id,
        "document_count": len(docs),
        "documents_by_status": _count_by_status(docs),
        "chunk_count": len(metadata_store.chunks_for_tenant(checked.tenant_id)),
        "vector_count": vector_store.count(checked.tenant_id),
        "embedding_cache_size": cache_size(),
        "response_cache_hit_rate": round(response_cache.hit_rate, 3),
        "retrieval_cache_hit_rate": round(retrieval_cache.hit_rate, 3),
    }


@router.get("/audit-log")
async def audit_log(ctx: AuthContext = Depends(get_auth_context)):
    require_role(Role.tenant_admin)(ctx)
    return metadata_store.audit_log[-200:]


@router.post("/dev-token")
async def dev_token(user_id: str, tenant_id: str, role: Role = Role.contributor):
    """DEV/DEMO ONLY -- mints a JWT without going through an IdP so the API is
    exercisable locally. Disabled in production deployments (see docs/security.md)."""
    if not settings.mock_mode:
        return {"error": "dev-token endpoint is disabled outside MOCK_MODE"}
    token = mint_dev_token(user_id, tenant_id, role)
    return {"access_token": token, "token_type": "bearer"}


def _count_by_status(docs) -> dict:
    counts: dict[str, int] = {}
    for d in docs:
        counts[d.status.value] = counts.get(d.status.value, 0) + 1
    return counts
