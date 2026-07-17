# Observability & Evaluation

## Logging

Structured JSON logs, one line per event, correlated by `request_id` and `trace_id`. Prompt
and completion are logged separately from application logs (different retention/access
policy — prompt logs may contain tenant data and need stricter access control than infra
logs).

## Metrics (Prometheus)

- Request rate, error rate, latency histograms per route (RED method).
- Retrieval-stage latency (BM25, vector search, rerank) broken out individually — this is
  what lets you say "reranking added 180ms" instead of "the query felt slow."
- Token usage and cost, tagged by tenant and model tier.
- Cache hit rate per cache tier (embedding/retrieval/response).
- Queue depth and worker throughput (ingestion pipeline health).

## Tracing (OpenTelemetry)

One trace per query spans: API → query understanding → hybrid retrieval → rerank → prompt
build → LLM gateway → streaming response. Each span carries tenant_id (as a low-cardinality
tag, not free text) so slow-tenant investigation doesn't require log grepping.

## Dashboards

- **Cost dashboard**: $ spend per tenant per day, broken down by embedding vs. LLM vs.
  infra, with anomaly alerts (a tenant's spend 3x'ing day over day pages someone).
- **Failure dashboard**: ingestion failures by cause (parse error, OCR failure, virus
  detected, oversized file), LLM gateway fallback-tier activations, timeout counts.
- **Hallucination dashboard**: sampled online faithfulness scores (see below) trended over
  time per tenant and per prompt version — this is the canary for "did our last prompt
  change make things worse."

## RAG evaluation (RAGAS-style)

Automated metrics computed against a golden dataset (curated Q&A pairs with known-correct
source documents) on every prompt/model/retrieval-config change, plus sampled against live
traffic:

| Metric | What it measures | Why it matters |
|---|---|---|
| Faithfulness | Does the generated answer's claims actually follow from the retrieved context? | Direct hallucination proxy |
| Context precision | Of the retrieved chunks, how many were actually relevant? | Measures retrieval/rerank quality, not generation |
| Context recall | Of the chunks that *should* have been retrieved (from golden set), how many were? | Catches retrieval misses even if generation looks fine |
| Answer relevancy | Does the answer actually address the question asked? | Catches on-topic-but-non-responsive answers |
| Groundedness | Stricter faithfulness variant requiring explicit citation support per claim | Used for the citation-checking guardrail |
| Latency / cost | p50/p95 latency, $ per query | Quality without a cost/latency budget isn't a real production metric |

**Automatic evaluation** runs as a CI gate: a prompt or retrieval-config change that drops
faithfulness or context recall below a threshold on the golden set fails the build, the same
way a broken unit test would. This is the MLOps analogue of a regression test suite, and
it's what stops "small prompt tweak" from silently degrading production quality.

## Testing pyramid

- **Unit tests**: chunking boundaries, prompt template rendering, RBAC rule evaluation.
- **Integration tests**: full ingestion → query round trip against a test tenant, using
  MOCK_MODE for the LLM/embedding calls (deterministic, free, fast).
- **Load tests** (Locust): simulate concurrent query and ingestion load to find the actual
  bottleneck (usually: DB connection pool or reranker throughput, not the LLM call).
- **Security tests**: prompt-injection golden set, file-upload fuzzing, authz boundary tests
  (user from tenant A must never successfully query tenant B's docs — this is a hard-fail
  test, not a soft warning).
- **Prompt tests / golden dataset regression**: described above.
