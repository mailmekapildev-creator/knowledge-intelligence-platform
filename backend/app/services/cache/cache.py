"""
Cache abstraction. Real deployments back this with Redis; the in-memory fallback here
means a Redis outage degrades to "no caching" rather than failing requests -- see
docs/failure-modes.md ("Redis fails"). Three tiers are modeled: embedding (handled in
embedder.py directly), retrieval-result, and full-response.
"""
from __future__ import annotations

import time


class TTLCache:
    def __init__(self, default_ttl_seconds: float = 300.0):
        self._store: dict[str, tuple[float, object]] = {}
        self.default_ttl = default_ttl_seconds
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: str, value, ttl_seconds: float | None = None) -> None:
        self._store[key] = (time.time() + (ttl_seconds or self.default_ttl), value)

    def invalidate_prefix(self, prefix: str) -> int:
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


response_cache = TTLCache(default_ttl_seconds=120.0)
retrieval_cache = TTLCache(default_ttl_seconds=300.0)


def make_query_cache_key(tenant_id: str, query: str) -> str:
    return f"{tenant_id}::{query.strip().lower()}"
