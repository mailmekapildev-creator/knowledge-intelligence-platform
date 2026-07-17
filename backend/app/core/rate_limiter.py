"""
Token-bucket rate limiter, per tenant. Enforced before a request reaches retrieval/LLM
stages -- protects against noisy-neighbor tenants and denial-of-wallet abuse (see
docs/security.md and docs/cost-and-scalability.md).

Production deployments back this with Redis (INCR + EXPIRE or a Lua-scripted bucket) so
limits are enforced consistently across API replicas; this in-memory version is
functionally equivalent for a single-process deployment and keeps local/demo runs
dependency-free.
"""
from __future__ import annotations

import time

from app.config import settings


class TokenBucket:
    def __init__(self, capacity: int, refill_per_minute: int):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_per_minute / 60.0  # tokens per second
        self.last_refill = time.time()

    def try_consume(self, amount: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class RateLimiter:
    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, tenant_id: str) -> bool:
        bucket = self._buckets.setdefault(
            tenant_id,
            TokenBucket(capacity=settings.rate_limit_requests_per_minute,
                        refill_per_minute=settings.rate_limit_requests_per_minute),
        )
        return bucket.try_consume()


rate_limiter = RateLimiter()


class RateLimitExceeded(Exception):
    pass
