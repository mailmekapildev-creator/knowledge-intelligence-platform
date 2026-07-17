# Cost Optimization & Scalability

## Cost levers, roughly in order of impact

1. **Caching** (embedding, retrieval-result, response) — the cheapest tokens are the ones
   you never generate. Response cache alone typically kills a large fraction of cost on
   FAQ-shaped workloads.
2. **Reranking instead of over-retrieving** — cheaper to rerank 50 candidates with a small
   cross-encoder than to stuff a bigger context window into the LLM and hope it attends to
   the right part.
3. **Model tiering** — cheap/fast model for simple factual queries, escalate to a stronger
   model only for complex/ambiguous queries (decided by a lightweight classifier or query
   complexity heuristic).
4. **Batch inference for embeddings** — batch chunk embedding calls at ingestion time; the
   per-call overhead and cost-per-token both improve with batching.
5. **Incremental/lazy indexing** — only re-embed changed chunks on document update (hash
   comparison), not the whole document.
6. **Streaming** — doesn't reduce total cost, but drastically improves perceived latency,
   which reduces retry/re-query behavior that *does* add cost.
7. **Rate limiting** — bounds worst-case cost from abuse or runaway client loops.
8. **Adaptive retrieval** — smaller top-k / cheaper reranking for simple queries, reserve
   the expensive path for queries that need it.
9. **TTL on caches** — balances cost savings against staleness (a cached answer about a
   policy that was just updated is worse than no cache).

## Scaling walk-through

| Scale | What breaks first | Mitigation |
|---|---|---|
| 10 users | Nothing — a single instance of everything handles this comfortably | — |
| 100 users | DB connection pool exhaustion if pooling isn't configured; LLM API rate limits if no backoff | Connection pooler (PgBouncer), gateway-level backoff/retry |
| 10,000 users | Backend API CPU-bound on concurrent request handling; reranker becomes a throughput bottleneck (cross-encoders are not free) | Horizontal autoscaling on the API tier; batch reranking; consider a dedicated inference server (e.g., a small GPU pool) for the reranker |
| 1,000,000 documents | Ingestion throughput bound by worker pool size and OCR throughput specifically (OCR is the slowest parser by a wide margin) | Scale worker pool on queue depth; route OCR-needing docs to a dedicated worker pool so they don't starve fast-path text documents |
| 100,000,000 chunks | ANN index build/query latency degrades on a single-node vector store; Postgres/pgvector stops being the right choice | Migrate to a sharded vector engine (Milvus) — this is exactly the upgrade path documented in ADR-002, not a rewrite |

## Scaling mechanisms

- **Autoscaling**: HPA on the API tier keyed on CPU + request latency; worker pool
  autoscaled on queue depth (a much better signal than CPU for a queue-consumer workload).
- **Load balancing**: standard L7 load balancer in front of the API tier; sticky sessions
  deliberately avoided (stateless API is what makes this trivial).
- **Queue-based ingestion**: absorbs ingestion bursts without back-pressuring the query
  path; a 50,000-document bulk upload degrades ingestion latency, not query latency.
- **Async processing everywhere in the ingestion path**: nothing in ingestion holds an open
  HTTP connection past the initial "accepted" response.

## Bottleneck honesty

The three things that actually tend to bite in production RAG systems, in the order teams
usually discover them the hard way: (1) the reranker's throughput ceiling, because it's easy
to forget it's a model too, not free lexical scoring; (2) OCR throughput on scanned-document-heavy
tenants, because it's 10–50x slower than plain-text parsing per page; and (3) vector index
rebuild/compaction time as delete/update volume grows, because ANN indexes are not built to
be updated as cheaply as they're built to be queried.
