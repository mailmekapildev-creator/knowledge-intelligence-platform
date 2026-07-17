# Ingestion Pipeline & Chunking Strategy

## Supported formats and parsing challenges

| Format | Parser | Main challenge |
|---|---|---|
| PDF (text) | `pdfplumber` / `pymupdf` | Multi-column layouts break naive top-to-bottom text extraction; tables need explicit table-extraction, not raw text dump |
| PDF (scanned) | OCR (Tesseract / cloud OCR) | Image quality, skew, handwriting; OCR errors silently corrupt downstream retrieval if not confidence-scored |
| Word (.docx) | `python-docx` | Tracked changes/comments must be deliberately included or excluded (compliance docs often need the redline history) |
| PowerPoint (.pptx) | `python-pptx` | Speaker notes vs. slide text are different signal — kept as separate chunk metadata, not concatenated |
| Excel/CSV | `openpyxl` / `pandas` | Tabular data doesn't chunk like prose — rows need to be summarized or chunked by sheet/table, not by character count |
| Images | OCR + optional vision captioning | Diagrams/screenshots often carry meaning OCR can't extract (arrows, layout) |
| Email (.eml) | `email` stdlib + header parsing | Thread quoting creates duplicate content across messages; need thread-aware dedup |
| HTML | `BeautifulSoup` | Nav/boilerplate stripping; without it, every chunk is 80% site chrome |
| Markdown | Header-aware splitter | Preserve heading hierarchy as metadata for parent-child retrieval |
| ZIP | Recursive unpack | Zip bombs / path traversal — validated and size-capped before recursion (security concern, not just parsing) |

## Preprocessing

- Encoding normalization (force UTF-8), whitespace/control-character stripping.
- Language detection (routes to language-appropriate chunking/embedding where relevant).
- PII detection pass (regex + NER model) — flags but does not silently delete; tenant policy
  decides mask vs. reject vs. allow.

## Metadata extraction

Captured per document: source filename, mime type, page/slide count, author (if present in
doc properties), created/modified timestamps, tenant_id, ACL tags, content hash (for
dedup/versioning), ingestion timestamp, parser version (so we can identify docs that need
re-parsing after a parser bugfix).

## Duplicate detection

Content-hash (SHA-256 of normalized text) for exact duplicates; MinHash/SimHash for
near-duplicates (same contract re-uploaded with a signature page added). Exact duplicates
are linked, not re-embedded (cost saving). Near-duplicates are flagged for a human/admin
decision rather than auto-merged, since near-duplicate contracts are often *meaningfully*
different (that's usually why there are two).

## Versioning

New upload of a previously-seen document (by tenant + filename + fuzzy content match)
creates a new version row linked to the same `document_group_id`. Old chunks are marked
`superseded_at`, not deleted immediately — queries default to latest version, but
point-in-time queries (compliance: "what did the policy say in March?") are possible.

---

## Chunking strategy comparison

| Strategy | How it works | Best for | Weakness |
|---|---|---|---|
| Fixed-size | Split every N characters/tokens with overlap | Simple, predictable cost | Cuts sentences/tables mid-thought; worst semantic coherence |
| Sentence-based | Split on sentence boundaries, group to target size | General prose | Doesn't respect document structure (headers, sections) |
| Recursive character | Try paragraph → sentence → word splits in order until size fits | Robust default for mixed prose | Still structure-agnostic |
| Semantic chunking | Embed sentences, split where semantic similarity drops | Best coherence for dense prose (policies, legal text) | Extra embedding calls at ingest time = cost |
| Markdown/header-aware | Split at heading boundaries, keep hierarchy as metadata | Docs with clear structure (wikis, READMEs, policies) | Useless on unstructured text |
| Code-aware | Split at function/class boundaries using an AST/tree-sitter parser | Source code, notebooks | Not applicable to prose |
| Parent-child | Small chunks for retrieval precision, linked to a larger parent chunk returned to the LLM for context | Balances retrieval precision with generation context | More storage, more indexing complexity |
| Adaptive | Chunk size varies by content density (e.g., smaller chunks for dense legal clauses, larger for narrative text) | Mixed corpora | Requires tuning per content type; hardest to reason about in production |

**Decision:** default to **recursive character chunking with parent-child linking**
(chunk_size=400 tokens, overlap=50, parent window=1200 tokens) as the general-purpose
default, with **markdown/header-aware chunking** for structured docs and **code-aware
chunking** for anything under `/src` or `.ipynb`. Semantic chunking is offered as an
opt-in for tenants who've shown it matters in their eval numbers — not on by default,
because the extra embedding cost isn't justified until measured. See
[ADR-004](adr/004-chunking-strategy.md).
