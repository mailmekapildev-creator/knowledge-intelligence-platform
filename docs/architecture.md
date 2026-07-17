# System Architecture

## Design principles

1. **Ingestion and query are separate scaling domains.** Ingestion is bursty, batchable, and
   latency-tolerant. Query is latency-critical and must not be blocked by ingestion load.
   This is why ingestion goes through a queue and query does not.
2. **Every component that can fail independently gets a timeout and a fallback.** See
   [`failure-modes.md`](failure-modes.md).
3. **Tenant isolation is enforced at more than one layer.** Application filtering alone is
   not defense in depth.
4. **Cache before you scale, scale before you throw a bigger model at it.**

## Component inventory

### Frontend
Thin client (chat UI + admin console). Talks only to the Backend API, never directly to the
LLM provider, vector DB, or object storage — this keeps API keys and infra credentials off
the client and lets us change backends without a client release.

### Backend API (FastAPI)
Stateless, horizontally scalable. Owns request validation, auth enforcement, rate limiting,
and orchestration of the query pipeline. Stateless-ness is why we can scale it with a plain
HPA instead of sticky sessions.

### Authentication Service
JWT-based session tokens issued after OAuth2/OIDC login (delegated to an identity provider —
Auth0/Okta/Cognito rather than homegrown, because credential storage is a liability center,
not a differentiator). Tenant ID and role claims are embedded in the JWT and re-validated on
every request server-side (never trust client-asserted tenant_id).

### Document Ingestion Service
Accepts uploads, writes the raw file to object storage, writes a metadata row (status=
`pending`), and enqueues a job. Returns immediately — ingestion is async by design so a
100MB PDF doesn't hold an HTTP connection open or block the request pool.

### Parsing Service (worker)
Format-specific parsers (PDF, DOCX, PPTX, XLSX, images via OCR, email/EML, HTML, Markdown,
CSV, ZIP recursively). Isolated into its own worker step because parsing failure is common
(corrupt files, password-protected PDFs, scanned images) and should not crash the whole
pipeline — it fails the one document and marks it `failed_parsing` with a reason.

### Chunking Service (worker)
Takes parsed text/structure and produces chunks with metadata (source doc, page, section,
parent chunk id). Strategy is pluggable per document type (see
[`ingestion-and-chunking.md`](ingestion-and-chunking.md)).

### Embedding Service (worker)
Batches chunks (batching matters for cost — most embedding APIs charge per call *and* the
GPU/accelerator amortizes better over batches), calls the embedding model, and writes vectors.
Embedding cache (hash of chunk text → vector) avoids re-embedding unchanged content on
re-ingestion.

### Vector Database
Stores chunk embeddings + metadata for ANN search, namespaced per tenant. See comparison in
[`tech-stack.md`](tech-stack.md).

### Metadata Store (Postgres)
System of record for documents, chunks (text + pointers, not vectors), tenants, users,
permissions, and audit log. Postgres, not the vector DB, is the source of truth — the vector
index can be rebuilt from Postgres, not the other way around. This matters for the "vector
DB fails" failure mode.

### Object Storage (S3/MinIO)
Raw file storage. Immutable, versioned (supports document versioning requirement).

### Search Service / Retriever
Orchestrates hybrid search: fires BM25 (lexical) and vector (semantic) search in parallel,
merges with reciprocal rank fusion, applies metadata filters (tenant, doc type, date range,
ACL), then hands candidates to the reranker.

### Cross-Encoder Reranker
Bi-encoder retrieval (fast, approximate) over-fetches (e.g., top 50), then a cross-encoder
reranks to the true top-k (e.g., 5–8) before it hits the prompt. This is the single highest
leverage change for answer quality per dollar — cheaper than a bigger LLM, and it's why we
don't just crank up vector-search top-k and hope.

### Prompt Builder
Assembles the final prompt: system instructions (grounding + citation format + refusal
policy), retrieved context (compressed if needed), conversation memory (summarized, not raw,
past a token budget), and the user question. Templated and versioned (prompt versioning is
part of MLOps here, not an afterthought).

### LLM Gateway
Provider-agnostic abstraction over the model call. Responsibilities: retries with backoff,
timeout enforcement, per-tenant rate limiting, cost/token logging, and a fallback model tier
if the primary model errors or times out. This is what makes "LLM API fails" a degraded
experience instead of a full outage.

### Response Streaming
Server-Sent Events from Backend → client, token-by-token, so perceived latency (time to
first token) is what users experience rather than total generation time.

### Caching Layer (Redis)
Three cache tiers: (1) embedding cache, (2) retrieval-result cache (same query + same corpus
version → same candidates), (3) full response cache (for FAQ-style repeated questions, with
a short TTL and cache-bust on source-document update).

### Rate Limiter
Token-bucket per tenant and per user, enforced at the gateway before the request reaches the
expensive part of the pipeline. Protects against noisy-neighbor tenants and runaway agents/
scripts.

### Message Queue (e.g., SQS / RabbitMQ / Redis Streams)
Decouples ingestion API from the worker pool. Gives us backpressure (queue depth is a real
signal for autoscaling workers) and lets ingestion survive worker crashes (message is
redelivered, not lost).

### Worker Services
Horizontally scalable pool consuming the queue, running parse → chunk → embed → index.
Scaled independently from the API tier because ingestion load and query load do not
correlate.

### Monitoring / Tracing (OpenTelemetry + Prometheus + Grafana)
Every request gets a trace spanning API → retriever → reranker → LLM gateway, so a slow
query can be attributed to a specific stage instead of "the LLM is slow" as a default guess.

### Evaluation Pipeline
Offline (golden dataset regression on every prompt/model change) and online (sampled live
traffic scored for faithfulness/relevance) — see
[`observability-and-evaluation.md`](observability-and-evaluation.md).

### Admin Dashboard
Per-tenant cost, latency, hallucination-rate, and usage dashboards, plus document management
(reindex, delete, view ingestion failures).

## Why not simpler?

The honest counter-argument: for a single-tenant, low-QPS internal tool, you could collapse
half of this into one service. This architecture is deliberately over-built relative to a
weekend project *on purpose* — the point of the repo is to demonstrate the decision-making
for when this complexity is warranted (see the Recruiter Expectations doc), not to claim
every project needs all of it on day one.
