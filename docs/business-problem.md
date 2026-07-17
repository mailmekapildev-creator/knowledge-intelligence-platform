# Business Problem

## Use case

**"Enterprise Knowledge Copilot"** — a multi-tenant platform that lets internal teams
(Legal, Compliance, Support, Engineering) ask natural-language questions against their own
private document corpora (contracts, policies, runbooks, ticket histories, PDFs, slide
decks) and get cited, grounded answers instead of hallucinated ones.

This is deliberately modeled as **multi-tenant B2B SaaS**, not a single-user chatbot,
because that's what forces the interesting engineering decisions: tenant isolation, RBAC,
per-tenant rate limits, per-tenant cost attribution, and noisy-neighbor protection.

## Target users

- **End users** (knowledge workers): ask questions, get cited answers, drill into sources.
- **Tenant admins**: manage document corpora, users, and access policies for their org.
- **Platform admins** (us): monitor cost, latency, hallucination rate, and abuse across tenants.

## Business value

- Reduces time-to-answer for policy/compliance/support questions from "search + read + ask a
  colleague" (often 15–30 min) to a cited answer in seconds.
- Reduces duplicate work: support agents no longer re-derive answers already documented
  elsewhere.
- Auditable: every answer is traceable to source documents, which matters for compliance
  and legal use cases specifically.

## Expected scale (design targets, not initial launch)

| Dimension | Target |
|---|---|
| Tenants | 50–500 |
| Concurrent users | 10 → 10,000 (design for 3 orders of magnitude) |
| Documents indexed | up to 1,000,000 |
| Chunks in vector store | up to 100,000,000 |
| Queries/day | 500,000 at scale |
| Ingestion throughput | 10,000 documents/day sustained, bursts to 50,000 |

## SLAs / latency targets

| Operation | Target (p50) | Target (p95) |
|---|---|---|
| Query (retrieval + generation, streamed) | first token < 800ms | first token < 2.5s |
| Document ingestion (small doc, < 20 pages) | < 30s to searchable | < 2 min |
| Availability | 99.9% for query path | 99.5% for ingestion path (async, can queue) |

Ingestion is intentionally given a looser SLA than query — it's async by design, which is
itself a scalability decision (see [`cost-and-scalability.md`](cost-and-scalability.md)).

## Security requirements

- Every query and every document is scoped to a tenant; cross-tenant data leakage is a
  sev-1, not a bug.
- Row-level and vector-store-level tenant isolation (not just application-level filtering —
  defense in depth).
- PII detection/masking on ingestion for regulated tenants.
- Full audit log of who asked what, what documents were retrieved, and what was answered.

## Compliance considerations

- Data residency: tenants may require documents/embeddings to stay in a specific region.
- Right to deletion: deleting a document must remove it from object storage, metadata DB,
  *and* the vector index (this is harder than it sounds — see ADR-003).
- SOC 2 style requirements: access logging, encryption at rest and in transit, least-privilege
  IAM.

## Multi-tenancy requirements

Three isolation models were considered (see [ADR-001](adr/001-multi-tenancy-model.md)):

1. **Silo** (separate DB/vector index per tenant) — strongest isolation, highest cost.
2. **Pool with tenant_id filtering** — cheapest, weakest isolation guarantees.
3. **Hybrid: shared infrastructure, per-tenant logical namespaces** (chosen) — tenant_id is
   enforced at the vector index namespace level *and* at the application/query layer, giving
   isolation closer to (1) at cost closer to (2). Large/regulated tenants can be promoted to
   dedicated silos without a re-architecture.
