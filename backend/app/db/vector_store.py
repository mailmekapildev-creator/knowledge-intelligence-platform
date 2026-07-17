"""
Vector store abstraction. Ships with an in-memory implementation (namespaced per
tenant, exact cosine search) so the portfolio build has zero external dependencies.

The interface is intentionally shaped like a pgvector/Milvus client (namespace = tenant,
upsert/search/delete by id) so swapping the backing engine per docs/tech-stack.md and
ADR-002 is a class swap, not a rewrite of callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class VectorRecord:
    chunk_id: str
    tenant_id: str
    vector: list[float]
    metadata: dict = field(default_factory=dict)


class InMemoryVectorStore:
    def __init__(self):
        # namespaced per tenant, mirroring the production namespace-per-tenant model (ADR-001)
        self._by_tenant: dict[str, dict[str, VectorRecord]] = {}

    def upsert(self, tenant_id: str, chunk_id: str, vector: list[float], metadata: dict) -> None:
        ns = self._by_tenant.setdefault(tenant_id, {})
        ns[chunk_id] = VectorRecord(chunk_id=chunk_id, tenant_id=tenant_id,
                                     vector=vector, metadata=metadata)

    def delete(self, tenant_id: str, chunk_id: str) -> None:
        self._by_tenant.get(tenant_id, {}).pop(chunk_id, None)

    def delete_document(self, tenant_id: str, document_id: str) -> int:
        ns = self._by_tenant.get(tenant_id, {})
        to_remove = [cid for cid, rec in ns.items()
                     if rec.metadata.get("document_id") == document_id]
        for cid in to_remove:
            del ns[cid]
        return len(to_remove)

    def search(self, tenant_id: str, query_vector: list[float], top_k: int,
               metadata_filter: dict | None = None) -> list[tuple[str, float, dict]]:
        ns = self._by_tenant.get(tenant_id, {})
        if not ns:
            return []
        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q) or 1.0

        scored = []
        for rec in ns.values():
            if metadata_filter and not _matches(rec.metadata, metadata_filter):
                continue
            v = np.array(rec.vector, dtype=np.float32)
            v_norm = np.linalg.norm(v) or 1.0
            score = float(np.dot(q, v) / (q_norm * v_norm))
            scored.append((rec.chunk_id, score, rec.metadata))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def count(self, tenant_id: str) -> int:
        return len(self._by_tenant.get(tenant_id, {}))


def _matches(metadata: dict, filt: dict) -> bool:
    for k, v in filt.items():
        if metadata.get(k) != v:
            return False
    return True


vector_store = InMemoryVectorStore()
