# ADR-002: Vector Database Choice

**Status:** Accepted (with a scaling upgrade path)

## Context
Need ANN vector search with metadata filtering, tenant isolation, and a reasonable ops
footprint at both small scale (portfolio/demo, low QPS) and the design-target scale (100M+
chunks).

## Options considered
FAISS, Pinecone, Milvus, Weaviate, Chroma, pgvector — full comparison in
[`tech-stack.md`](../tech-stack.md).

## Decision
Default to **pgvector** for local/dev/small-scale deployments (fewer systems to run,
transactional consistency with the metadata store, sufficient recall/latency below roughly
5–10M vectors). Document **Milvus** as the production path once vector count or QPS exceeds
what a single Postgres instance handles well.

## Consequences
- Reviewer/interviewer can stand up the whole system with `docker compose up` — no external
  vector DB account needed.
- Migration path to Milvus requires re-indexing (embeddings are portable; the index
  structure is not), which is an accepted one-time cost at the point scale actually demands
  it — not paid upfront for a scale the project doesn't have yet.
- Rejected Pinecone as the default despite excellent DX, specifically because of recurring
  cost and vendor lock-in for what is meant to be a demonstrably portable architecture.
