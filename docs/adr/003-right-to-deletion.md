# ADR-003: Right-to-Deletion Across Object Storage, Metadata DB, and Vector Index

**Status:** Accepted

## Context
Compliance requires that deleting a document actually removes it — including its vectors.
Most ANN indexes are not built for cheap point deletes (some require rebuild/compaction).

## Decision
Deletion is a two-phase, asynchronous operation:
1. **Immediate**: document marked `deleted` in Postgres (source of truth), removed from
   object storage, and excluded from all *future* query-time metadata filters immediately —
   so it's functionally invisible right away even before vector cleanup completes.
2. **Async**: a background job removes the corresponding vectors from the vector index
   (soft-delete + periodic compaction for engines where hard delete is expensive).

## Consequences
- Satisfies "right to deletion" in practice (invisible immediately) without requiring
  synchronous, potentially slow index compaction on the request path.
- Requires a scheduled reconciliation job and monitoring to guarantee phase 2 actually
  completes (a stuck async delete is a compliance risk, so it's tracked with an SLA and
  alerting, not fire-and-forget).
