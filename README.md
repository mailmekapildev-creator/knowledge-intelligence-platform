# Knowledge Intelligence Platform (KIP)

An enterprise-grade Retrieval-Augmented Generation (RAG) platform — not a chatbot demo.
KIP is designed the way a Staff/Principal engineer would design a multi-tenant document
intelligence system meant to survive a production incident review, a security audit, and
a cost review, in that order.

> **Status:** Reference architecture + runnable engineering skeleton. Ships in `MOCK_MODE`
> by default so it runs end-to-end with **zero cloud cost and no API keys** — flip one env
> var to point it at real infra (Postgres/pgvector, Redis, S3, Claude API).

---

## Why this exists

Most "RAG chatbot" portfolio projects are: `PDF -> chunk -> embed -> vector search -> LLM call`.
That demonstrates you can call an SDK. It does not demonstrate you can build the systems
around the model — ingestion at scale, hybrid retrieval, caching, security, observability,
evaluation, and graceful degradation when a downstream dependency fails.

This repo is structured so a hiring panel can look at the folder tree and the docs and see
each of those concerns addressed explicitly, with the trade-offs written down rather than
implied.

## Business problem this is modeled on

Multi-tenant internal knowledge search for a mid-size enterprise (think: legal, compliance,
engineering, and support teams each with their own private document corpus, sharing one
platform). See [`docs/business-problem.md`](docs/business-problem.md) for target users,
SLAs, scale assumptions, and compliance constraints.

## Architecture at a glance

```
Client (Web) ──▶ API Gateway ──▶ Auth Service (JWT/OAuth2, RBAC)
                                    │
                    ┌───────────────┼──────────────────────┐
                    ▼                                       ▼
           Ingestion Service                          Query Service
           (upload → queue)                    (hybrid retrieve → rerank →
                    │                           prompt build → LLM → stream)
                    ▼                                       │
             Worker Pool (async)                            │
       parse → chunk → embed → index                        │
                    │                                       │
         ┌──────────┼──────────┐                             │
         ▼          ▼          ▼                             ▼
   Object Store  Metadata DB  Vector DB  ◀──────────── Cache (Redis) + Rate Limiter
   (S3/MinIO)   (Postgres)   (pgvector/                LLM Gateway (provider-agnostic)
                              Milvus)                  Evaluation Pipeline (RAGAS)
                                                        Observability (OTel + Prometheus)
```

Full write-up with the reasoning behind every box: [`docs/architecture.md`](docs/architecture.md).

## Repository layout

```
knowledge-intelligence-platform/
├── backend/               FastAPI service (ingestion, retrieval, LLM gateway, admin API)
├── frontend/              Minimal chat + admin UI (vanilla JS, no build step)
├── evaluation/            RAGAS-style automated retrieval/answer quality evaluation
├── infrastructure/        docker-compose, Kubernetes manifests, Terraform stubs
├── tests/                 unit / integration / load tests
├── docs/                  architecture, tech stack, ADRs, interview questions, runbooks
├── scripts/               setup, seed data, load-test runner
└── .github/workflows/     CI pipeline
```

## Quickstart (mock mode — no keys needed)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MOCK_MODE=true
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the OpenAPI console, or open `frontend/index.html`
directly in a browser (it talks to `localhost:8000`).

## Quickstart (full stack, real infra)

```bash
cd infrastructure
docker compose up -d          # postgres+pgvector, redis, minio, backend, worker
export MOCK_MODE=false
export ANTHROPIC_API_KEY=sk-...
```

## Documentation index

| Doc | Contents |
|---|---|
| [`docs/business-problem.md`](docs/business-problem.md) | Target users, scale, SLAs, compliance |
| [`docs/architecture.md`](docs/architecture.md) | Every service, why it exists, alternatives considered |
| [`docs/tech-stack.md`](docs/tech-stack.md) | Stack choices with trade-offs vs. alternatives |
| [`docs/ingestion-and-chunking.md`](docs/ingestion-and-chunking.md) | Parsing, OCR, chunking strategy comparison |
| [`docs/retrieval.md`](docs/retrieval.md) | Hybrid search, HyDE, reranking, adaptive top-k |
| [`docs/security.md`](docs/security.md) | AuthN/AuthZ, prompt injection defense, attack vectors |
| [`docs/observability-and-evaluation.md`](docs/observability-and-evaluation.md) | Metrics, tracing, RAGAS, hallucination dashboard |
| [`docs/cost-and-scalability.md`](docs/cost-and-scalability.md) | Cost levers, scaling from 10 → 10M docs |
| [`docs/failure-modes.md`](docs/failure-modes.md) | What happens when each dependency dies |
| [`docs/adr/`](docs/adr) | Architecture Decision Records |
| [`docs/interview-questions.md`](docs/interview-questions.md) | 100 questions this project should let you answer cold |
| [`docs/recruiter-and-interview-guide.md`](docs/recruiter-and-interview-guide.md) | What reviewers actually look for |

## License

MIT — use freely for your own portfolio.
