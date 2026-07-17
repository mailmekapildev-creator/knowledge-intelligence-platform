# Retrieval Pipeline & Prompt Engineering

## Why hybrid search

Pure vector search misses exact-match signals (part numbers, error codes, defined terms in
contracts) that lexical search catches trivially. Pure BM25 misses paraphrase/semantic
matches. Production RAG systems that ship with only one of the two are leaving accuracy on
the table for a well-understood reason, which is why this is non-negotiable rather than a
"nice to have."

## Pipeline stages

1. **Query understanding**
   - *Query expansion*: generate 2–3 paraphrases of the user query to widen recall.
   - *HyDE (Hypothetical Document Embeddings)*: ask the LLM to draft a hypothetical answer,
     embed *that*, and search with it — works well when the query is short and the answer
     vocabulary differs from the question vocabulary (common in support/legal search).
   - *Multi-query retrieval*: run retrieval for the original query + expansions, merge
     results.
   - *Self-query retrieval*: LLM extracts structured filters from natural language (e.g.
     "contracts signed after 2023 with Acme Corp" → `date > 2023-01-01 AND party=Acme`),
     converted to metadata filters rather than relying on the vector search to "understand" dates.

2. **Hybrid retrieval**
   - BM25 (lexical) and vector (semantic, ANN) run **in parallel**, each returns top ~50.
   - Merge via Reciprocal Rank Fusion (simple, no extra model call, tunable per-tenant).
   - Metadata filters (tenant_id, ACL, doc type, date range) applied at the query level, not
     post-filtered — post-filtering after ANN search can return fewer results than requested
     if most top-k hits get filtered out.

3. **Reranking**
   - Cross-encoder reranks the merged ~50–100 candidates down to top 5–8.
   - This is the step that actually determines answer quality most of the time — bi-encoder
     retrieval is optimized for recall, not precision; the reranker buys back precision
     cheaply.

4. **Context compression / parent-child expansion**
   - If the winning chunks are small (precision chunks), swap in their parent chunk for
     generation context, but only include distinct parents (dedup) and truncate to a token
     budget.
   - Long context is compressed via extractive summarization if the token budget would
     otherwise force dropping a relevant document entirely.

5. **Adaptive top-k**
   - Simple factual queries: fewer, tighter chunks (default 5).
   - Broad/comparative queries ("summarize our vendor contracts from 2023"): higher top-k,
     with model choice escalated to a stronger tier — this is a cost/quality tradeoff made
     explicitly, not left to whatever the default happens to return.

## Prompt design to minimize hallucination

- System prompt explicitly instructs: answer **only** from provided context; if the context
  doesn't contain the answer, say so rather than guessing.
- Every retrieved chunk is tagged with a citation ID; the model is instructed to cite
  `[doc_id:chunk_id]` inline, which is then rendered as a clickable source link in the UI and
  is also what the evaluation pipeline checks against (a citation to a chunk that doesn't
  support the claim is a faithfulness failure, caught automatically).
- Structured output: for admin/API consumers, responses can be requested as JSON matching a
  schema (answer, citations[], confidence) via tool calling / structured output mode, rather
  than parsing free text.
- Conversation memory: summarized past a token budget rather than included raw, so a long
  session doesn't silently crowd out retrieved context.
- Guardrails: a lightweight classifier/prompt check on the input for prompt-injection
  patterns before it reaches the main prompt (see [`security.md`](security.md)).

## Why not just "put everything in a huge context window"

Even with very large context windows available, dumping the whole corpus in-context is
neither cost-efficient (you pay for every token every request) nor more accurate — retrieval
naturally narrows to relevant content, which reduces the "needle in a haystack" attention
degradation large models exhibit with large irrelevant context. Retrieval is a precision
tool, not a workaround for a small context window.
