# 100 Interview Questions Based on This Project

Organized by category. The point isn't to memorize answers — it's to be able to defend the
decisions in this repo out loud, including the parts you'd do differently at a different
scale. Every question below should be answerable by pointing at a specific doc in this repo.

## System Design (1–15)
1. Walk me through the full request path for a user query, end to end.
2. Why is ingestion async but query synchronous/streamed?
3. How would you redesign this for a single-tenant, low-QPS internal tool? What would you cut?
4. What's the single point of failure in this architecture, and how is its blast radius limited?
5. How does the system behave differently at 10 users vs. 10,000?
6. Why is Postgres the source of truth instead of the vector database?
7. How would you add a new document type (e.g., Slack export) to the ingestion pipeline?
8. What would you change if this had to support real-time collaborative documents instead of static uploads?
9. How do you decide what goes in the synchronous request path vs. behind a queue?
10. What's your strategy for zero-downtime deploys of a schema change to the metadata DB?
11. How would this design change if the LLM provider had no streaming API?
12. Where would you introduce a message bus (Kafka) if ingestion volume grew 100x?
13. How do you avoid the reranker becoming a bottleneck at high QPS?
14. What's the failure domain boundary between the API tier and the worker tier, and why does that boundary exist?
15. How would you support offline/on-prem deployment for a data-residency-constrained customer?

## Machine Learning / GenAI (16–35)
16. Why hybrid search instead of pure vector search?
17. Explain Reciprocal Rank Fusion and why it's used to merge BM25 and vector results.
18. What does a cross-encoder reranker do differently from a bi-encoder, and why does that matter?
19. Explain HyDE and give a query type where it helps vs. where it doesn't.
20. What is context precision vs. context recall, and how do they diverge in practice?
21. How do you measure faithfulness automatically without a human in the loop?
22. Why is parent-child chunking used instead of just increasing chunk size?
23. When would you choose semantic chunking over recursive character chunking?
24. How do you decide embedding dimension and its cost/latency/accuracy trade-offs?
25. What's an embedding cache keyed on, and what invalidates it?
26. How would you detect that an embedding model needs to be replaced/upgraded?
27. Explain self-query retrieval and why it's more reliable than hoping the LLM infers filters from context.
28. What's the risk of skipping reranking entirely at low latency budgets?
29. How do you handle a query where the corpus genuinely has no answer?
30. What's your approach to evaluating multi-turn conversational RAG vs. single-turn?
31. How would you detect model/prompt regressions before they reach production?
32. What's the difference between a golden-dataset eval and sampled online evaluation?
33. How do you handle multilingual documents in a single tenant's corpus?
34. Explain adaptive top-k and how you'd decide the threshold for "simple" vs. "complex" query.
35. What are the failure modes of using cosine similarity as your only relevance signal?

## Distributed Systems (36–48)
36. Why is the queue a hard requirement rather than a nice-to-have for ingestion?
37. How do you get exactly-once (or effectively-once) processing semantics from an at-least-once queue?
38. What happens to an in-flight ingestion job if the worker pod is killed mid-processing?
39. How do you handle backpressure when ingestion arrives faster than workers can process?
40. Explain how autoscaling on queue depth differs from autoscaling on CPU, and why it matters here.
41. How do you keep the vector index and metadata DB consistent if one write succeeds and the other fails?
42. What consistency model does this system offer for "I just deleted a document, is it really gone?"
43. How would you shard the vector index across nodes as chunk count grows past a single node's capacity?
44. What's your retry/backoff strategy for calls to the LLM provider, and why does naive infinite retry cause problems?
45. How do you avoid duplicate processing when a queue message is redelivered?
46. What tracing strategy lets you attribute latency to a specific pipeline stage in a distributed request path?
47. How would you coordinate a rolling embedding-model migration without downtime?
48. What's the risk of synchronous cross-service calls in the ingestion pipeline, and how is it avoided here?

## Backend Engineering (49–58)
49. Why FastAPI and what does async give you here that a sync framework doesn't?
50. How is tenant_id trusted — where does it come from and why not the request body?
51. Walk through the rate limiter's algorithm and why token bucket over fixed window.
52. How do you structure the LLM Gateway so switching providers is a config change, not a rewrite?
53. What does the streaming response implementation look like end to end (SSE vs. WebSockets — why one)?
54. How do you validate uploaded files before they hit the parsing worker?
55. What's your approach to API versioning as the schema evolves?
56. How would you add caching without introducing stale-data bugs across tenants?
57. What's the connection pooling strategy for Postgres under concurrent load?
58. How do you structure error responses so the frontend can distinguish "retry me" from "don't retry"?

## Databases (59–66)
59. Why does Postgres double as both metadata store and (optionally) vector store?
60. What indexes matter most on the chunks table and why?
61. How does row-level security enforce tenant isolation at the DB layer?
62. What's the schema design trade-off between storing chunk text in Postgres vs. only pointers to object storage?
63. How do you handle schema migrations on a table with hundreds of millions of rows without downtime?
64. Why is document versioning modeled as new rows with `superseded_at` rather than in-place updates?
65. How would pgvector's HNSW/IVFFlat index choice affect recall/latency trade-offs?
66. What's your backup/restore strategy, and how does it interact with the vector index rebuild story?

## Cloud & Infrastructure (67–75)
67. Why Kubernetes here instead of a simpler PaaS (e.g., a managed container service)?
68. What does the Terraform module boundary look like — what's one module vs. split into several?
69. How do you handle secrets rotation without a redeploy?
70. What's your multi-region strategy if a tenant requires EU-only data residency?
71. How would you cost-model this system for a customer asking "what will 10,000 users cost us monthly"?
72. What's the CI/CD pipeline gate structure — what has to pass before a deploy ships?
73. How do canary and blue-green deployment differ, and which do you use for a prompt-template change vs. a backend code change?
74. How do you roll back a bad prompt version separately from a bad code deploy?
75. What's your disaster recovery RTO/RPO target for this system, and which component drives it?

## Security (76–84)
76. Walk through how you'd defend against a prompt injection embedded in an uploaded document.
77. Why is tenant isolation enforced at more than one layer instead of just an application-level filter?
78. How do you prevent a compromised document from poisoning retrieval for unrelated tenants/queries?
79. What's your file-upload validation pipeline, and what does it block?
80. How would you detect and respond to a tenant attempting to exfiltrate another tenant's data via crafted prompts?
81. What's the difference between authentication and authorization failures in your logging, and why log them differently?
82. How do you handle PII that a tenant explicitly wants indexed (not masked) for compliance reasons?
83. What's your approach to rate-limiting abuse without degrading legitimate high-volume tenants?
84. How would a SOC 2 auditor evaluate this system's access logging?

## Scalability (85–90)
85. What's the first component to fall over as document count grows past 1M, and why?
86. How do you scale OCR throughput specifically, separate from text-parsing throughput?
87. At what point does pgvector stop being the right choice, and what's the migration cost?
88. How would you handle a single tenant that's 100x larger than every other tenant (noisy neighbor)?
89. What's your approach to load testing this system realistically (not just hammering one endpoint)?
90. How do queue depth metrics inform worker autoscaling decisions better than CPU metrics?

## MLOps (91–96)
91. How is prompt versioning implemented, and how does a bad prompt version get rolled back?
92. What triggers the automatic golden-dataset regression check, and what's the failure threshold?
93. How do you track experiments across different chunking/reranking/model configurations?
94. What's your model registry story if you later fine-tune a custom reranker?
95. How does a canary rollout of a new LLM model tier work without impacting all tenants at once?
96. What's logged for every LLM call to make cost/quality regressions debuggable after the fact?

## Production Failures & Trade-offs (97–100)
97. The vector DB is down at 2am. What's the user-facing experience, and what paged someone?
98. A tenant's cost 5x'd overnight — walk through how you'd detect, diagnose, and contain it.
99. Retrieval quality silently degraded after a "small" prompt tweak — how would your evaluation pipeline have caught it before prod?
100. If you had to cut this system down to ship an MVP in two weeks, what would you keep and what would you explicitly defer, and why?
