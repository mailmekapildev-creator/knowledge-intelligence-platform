# Tech Stack & Rationale

Format: **Choice** — why, and what we gave up.

| Layer | Choice | Why | Alternatives considered |
|---|---|---|---|
| Frontend | Vanilla JS + minimal HTML (chat UI), React for admin console | No build step needed for the demo surface; keeps the reviewer's setup to zero. React for admin because that surface has real state/forms. | Next.js (heavier than needed for a portfolio scope), Streamlit (fast but reads as a notebook demo, not production UI) |
| Backend API | FastAPI (Python) | Async-native (matters for streaming + concurrent I/O to LLM/vector DB), automatic OpenAPI docs, Pydantic validation, huge ecosystem overlap with ML tooling | Node/Express (fine, but splits the stack across two languages for a solo/team project), Go (better raw throughput, worse ecosystem fit for embedding/eval tooling) |
| Auth | OAuth2/OIDC via Auth0/Cognito + JWT | Delegating identity to a provider avoids owning password storage, MFA, and breach liability | Homegrown auth (rejected — high liability, low differentiation) |
| Relational/metadata DB | PostgreSQL | Battle-tested, supports JSONB for flexible metadata, and pgvector lets it double as a vector store for small/medium scale without adding an extra system | MySQL (weaker JSON/extension story) |
| Vector database | pgvector (default/dev), Milvus (recommended at scale) | pgvector: one fewer moving part below ~5–10M vectors, transactional consistency with metadata. Milvus: purpose-built ANN engine, horizontal sharding, better recall/latency at 100M+ vectors | Pinecone (great DX, ongoing $, vendor lock-in), Weaviate (strong hybrid search built-in, extra ops surface), FAISS (library not a service — no persistence/replication out of the box) — full comparison in the table below |
| Object storage | S3 (prod), MinIO (local/dev, S3-compatible) | Standard, versioned, cheap, integrates with lifecycle policies for cold storage | Local filesystem (no durability/replication story) |
| Cache | Redis | De facto standard, supports TTL, pub/sub (for streaming fan-out), and doubles as the rate-limiter's token-bucket store | Memcached (no data structures, no pub/sub) |
| Queue | Redis Streams (dev), SQS or RabbitMQ (prod) | Redis Streams keeps local dev to one dependency; SQS for prod because it's managed, durable, and scales without ops | Kafka (justified at very high ingestion throughput, overkill below that) |
| Containers | Docker | Universal | — |
| Orchestration | Kubernetes (EKS/GKE/AKS) | HPA on queue depth + CPU, rolling/canary deploys, standard in enterprise environments | Nomad (less common in target job market) |
| CI/CD | GitHub Actions | Free for public repos, matches where the code lives, good matrix-build support | Jenkins (more ops overhead), GitLab CI (fine, just not where this repo lives) |
| IaC | Terraform | Cloud-agnostic, huge module ecosystem, plan/apply review workflow fits change-management requirements | Pulumi (good, smaller hiring pool familiarity), CloudFormation (AWS-only) |
| Monitoring/metrics | Prometheus + Grafana | Standard k8s-native metrics stack, free, pull-based fits dynamic pod IPs | Datadog (great, but $$$ and vendor lock-in for a portfolio project) |
| Logging | Structured JSON logs → Loki/ELK | Correlatable with traces via request ID | Plain stdout logs (works, but not queryable at scale) |
| Tracing | OpenTelemetry → Jaeger/Tempo | Vendor-neutral instrumentation; can be piped to any backend later | Vendor SDKs directly (lock-in) |
| Model serving (LLM) | Anthropic Claude API via LLM Gateway abstraction | Managed, no GPU ops burden, gateway layer means swapping providers is a config change | Self-hosted OSS LLM (justified only if data residency forbids external API calls — documented as an option, not the default) |
| Embeddings | `text-embedding-3-small`-class API model (default), sentence-transformers (self-hosted option) | API model: no infra, good quality/cost ratio. Self-hosted option documented for data-residency-constrained tenants | OpenAI ada-002 (older, worse cost/perf) |
| Reranking | Cross-encoder (e.g., `bge-reranker` / Cohere Rerank) | Order-of-magnitude cheaper than solving quality by increasing LLM context or model size | Skipping reranking entirely (rejected — measurably worse faithfulness in eval) |
| Evaluation | RAGAS + custom golden-dataset harness | Standard metrics (faithfulness, context precision/recall, answer relevancy) with an escape hatch for domain-specific checks | DeepEval (comparable; RAGAS chosen for broader adoption/citations in interviews) |
| Testing | pytest, Locust (load), Bandit (security static analysis) | Standard Python tooling, low ceremony | — |
| Secrets | Cloud provider secrets manager (AWS Secrets Manager / GCP Secret Manager) + `.env` for local | Never commit secrets; rotation support | Vault (justified at larger org scale, documented as upgrade path) |
| Feature flags | Simple config-service pattern (documented), Unleash/LaunchDarkly for prod | Enables canary/blue-green model and prompt rollouts without a redeploy | Hardcoded flags (rejected — blocks canary rollout story) |

## Vector database comparison (detail)

| | FAISS | Pinecone | Milvus | Weaviate | Chroma | pgvector |
|---|---|---|---|---|---|---|
| Type | Library | Managed service | Self-hosted/managed engine | Self-hosted/managed | Embedded/self-hosted | Postgres extension |
| Horizontal scaling | Manual sharding | Built-in | Built-in (sharded, distributed) | Built-in | Limited | Vertical mainly; scales with Postgres |
| Replication/backup | DIY | Managed | Managed (self-hosted needs setup) | Managed | DIY | Postgres-native (WAL, replicas) |
| Metadata filtering | Basic | Good | Good | Very good (hybrid built-in) | Basic | Excellent (it's SQL) |
| Cost at scale | Compute only | $$ recurring, scales with vectors | Infra cost, no per-vector fee | Infra cost | Low | Low, until index size hurts Postgres |
| Best fit here | Offline experimentation | Fast start, don't want ops | 10M+ vectors, need control | Need built-in hybrid + filtering | Prototyping | < 5–10M vectors, want one less system |

**Decision:** ship with pgvector by default (fewer moving parts for the reviewer to stand
up), document Milvus as the production upgrade path at scale. See
[ADR-002](adr/002-vector-database-choice.md).
