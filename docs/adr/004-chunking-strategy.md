# ADR-004: Default Chunking Strategy

**Status:** Accepted

## Context
Chunking strategy materially affects retrieval quality and cost. No single strategy is best
across all content types (see [`ingestion-and-chunking.md`](../ingestion-and-chunking.md)).

## Decision
- Default: recursive character chunking, 400 token target / 50 token overlap, with
  parent-child linking (parent window ~1200 tokens).
- Structured documents (Markdown, wikis): header-aware chunking, preserving heading
  hierarchy as metadata.
- Source code: AST/tree-sitter-based chunking at function/class boundaries.
- Semantic chunking available as an opt-in, not default, gated behind measured eval
  improvement for a given tenant's corpus.

## Consequences
- One predictable default covers the majority of prose documents without per-tenant tuning.
- Parent-child linking adds storage and indexing complexity (two chunk sizes tracked per
  document) in exchange for retrieval precision without sacrificing generation context —
  judged worth it based on eval improvement over flat chunking in internal testing.
- Semantic chunking's extra embedding cost at ingest time is not paid unless there's
  evidence it's needed, keeping the default cost-efficient.
