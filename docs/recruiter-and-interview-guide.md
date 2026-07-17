# What Reviewers Actually Look For

## What a Senior AI/ML Engineer (3–7 yrs) is expected to show
Not "I can call an LLM API" — that's table stakes. Expected: retrieval quality tuning
(hybrid search, reranking), cost-aware design, understanding of where latency actually goes
in a RAG pipeline, and the ability to explain *why* a chunking or retrieval choice was made,
not just that one was made.

## What a Staff Engineer is expected to show
System-level trade-offs: why async ingestion, why Postgres as source of truth, how failure
domains are isolated, how the design scales (or explicitly doesn't, yet) across three orders
of magnitude of load. A Staff-level review of this repo asks "what did you choose *not* to
build, and why" as much as what's here.

## What an Engineering Manager is expected to look for
Can this person's work be maintained by someone else? Are decisions written down (ADRs) or
only in the author's head? Is there a testing/eval strategy that would catch a regression
before a customer does? Does the project structure suggest they've shipped something real,
or only prototyped?

## What interviewers will actually ask
See [`interview-questions.md`](interview-questions.md) — but the meta-pattern across all of
them is: **"why this, and what did it cost you to choose it over the alternative?"** Every
section in this repo's docs is written to answer that pattern directly, not just describe
what was built.

## What GitHub reviewers look for in 90 seconds
1. Does the README explain the *problem*, not just list technologies?
2. Is there evidence of production concerns (tests, CI, docs, ADRs) or just a `main.py`?
3. Does it run? (`MOCK_MODE` exists specifically so a reviewer can verify this in under five
   minutes without needing your API keys.)
4. Are trade-offs written down, or does everything look like the only possible choice?

## Common mistakes this project deliberately avoids
- **"ChatGPT wrapper" smell**: a single file that calls an LLM SDK with retrieved context
  and nothing else. This repo separates ingestion, retrieval, reranking, prompt building,
  and generation into distinct, independently-scalable, independently-testable services —
  and explains why that separation matters, not just that it exists.
- **No evaluation story**: shipping a RAG system with no way to know if it got worse.
  Addressed with the RAGAS-style golden-dataset CI gate.
- **No failure-mode thinking**: "what if the vector DB is down" being an unanswered
  question. Addressed explicitly in [`failure-modes.md`](failure-modes.md).
- **Decisions with no reasoning attached**: picking a vector DB or chunking strategy with no
  documented alternative considered. Addressed via ADRs.
- **All-or-nothing cost thinking**: no cache, no batching, no model tiering — just "call the
  biggest model for everything." Addressed in
  [`cost-and-scalability.md`](cost-and-scalability.md).

## How to talk about this project in an interview
Don't present it as "I built a RAG chatbot." Present it as: *"I designed a multi-tenant
document intelligence platform and made the same trade-offs a team would face in
production — here's what I chose, here's the alternative I rejected and why, and here's
where the design explicitly doesn't scale yet and what the upgrade path looks like."* That
framing is the difference between a portfolio project and a system-design answer with code
attached.
