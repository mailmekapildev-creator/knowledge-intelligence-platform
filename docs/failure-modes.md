# Failure Scenarios & Graceful Degradation

Principle: every external dependency gets a timeout, and every timeout has a defined
fallback behavior — "the request hangs" is never an acceptable answer to "what happens if X
fails."

| Failure | Behavior |
|---|---|
| **LLM API fails/times out** | LLM Gateway retries with backoff (bounded), then fails over to a secondary model/provider tier if configured; if all fail, the API returns a clear error with the retrieved citations still included (so the user at least gets the sources, not a blank failure) |
| **Vector DB fails** | Fall back to BM25-only retrieval (degraded but functional) rather than failing the whole query; alert fires; since Postgres metadata store is the system of record, the vector index can be rebuilt without data loss |
| **Redis (cache) fails** | Cache calls wrapped with a short timeout and treated as cache-miss on error — system runs slower (no caching) but does not go down; rate limiter falls back to a conservative in-memory local limit rather than failing open or failing closed entirely |
| **Postgres (metadata DB) fails** | This is the one true hard dependency — query path returns a clear 503 rather than a partial/incorrect response; read replicas absorb read load to reduce the chance of this in the first place |
| **Queue fails** | Ingestion API returns a 503 for new uploads (fails closed — better to reject an upload than silently drop it); in-flight messages are durable in the queue's backing store and are redelivered once it recovers |
| **OCR fails on a document** | That document is marked `failed_ocr` with the reason surfaced in the admin dashboard; other documents in the batch are unaffected (isolated per-document failure, not a pipeline-wide halt) |
| **Embedding model changes/deprecates** | Embeddings are versioned (model_id + dimension stored per vector); a model change triggers a background re-embedding job rather than breaking retrieval for un-migrated content immediately — old and new embeddings can coexist in different namespaces during migration |
| **Rate limits occur (LLM provider side)** | Gateway respects `Retry-After`, queues the request briefly if within SLA budget, or fails over to the secondary model tier |
| **Timeouts occur (any stage)** | Every stage has an explicit timeout (e.g., retrieval 2s, rerank 500ms, LLM first-token 5s); a timeout at reranking falls back to un-reranked vector results rather than failing the query outright — degraded quality beats no answer |

## Design consequence

This table is why the architecture insists on: Postgres as source of truth (not the vector
DB), async ingestion (not synchronous), a gateway abstraction around the LLM call (not a
direct SDK call inline), and cache-miss-on-error semantics everywhere caching is used. None
of these are incidental — they're the direct answer to "what's the blast radius when this
dependency has a bad day."
