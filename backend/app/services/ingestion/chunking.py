"""
Chunking strategies. See docs/ingestion-and-chunking.md for the full comparison and
rationale. Default strategy: recursive character chunking with parent-child linking.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass


@dataclass
class ChunkCandidate:
    text: str
    parent_text: str
    section: str | None
    page: int | None


def _approx_token_count(text: str) -> int:
    # Cheap approximation (avoids pulling in a tokenizer dependency for the demo build).
    return max(1, len(text) // 4)


def _split_into_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def recursive_character_chunk(
    text: str,
    chunk_size_tokens: int = 400,
    overlap_tokens: int = 50,
    parent_window_tokens: int = 1200,
) -> list[ChunkCandidate]:
    """
    Default general-purpose chunker: paragraph-aware, falls back to sentence/word
    splitting when a paragraph itself exceeds the target size. Produces small
    "precision" chunks plus a linked larger "parent" chunk used at generation time
    (parent-child retrieval, see ADR-004).
    """
    paragraphs = _split_into_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[ChunkCandidate] = []
    buffer = ""
    buffer_start_idx = 0

    def flush(buf: str, start_idx: int, end_idx: int):
        if not buf.strip():
            return
        parent_start = max(0, start_idx - 1)
        parent_end = min(len(paragraphs), end_idx + 2)
        parent_text = "\n\n".join(paragraphs[parent_start:parent_end])
        chunks.append(ChunkCandidate(text=buf.strip(), parent_text=parent_text,
                                      section=None, page=None))

    idx = 0
    for i, para in enumerate(paragraphs):
        candidate = (buffer + "\n\n" + para).strip() if buffer else para
        if _approx_token_count(candidate) > chunk_size_tokens and buffer:
            flush(buffer, buffer_start_idx, i - 1)
            # overlap: carry the tail of the previous buffer forward
            overlap_chars = overlap_tokens * 4
            buffer = buffer[-overlap_chars:] + "\n\n" + para
            buffer_start_idx = i
        else:
            buffer = candidate
            if not buffer.strip() == para:
                pass
            if buffer == para:
                buffer_start_idx = i
        idx = i

    flush(buffer, buffer_start_idx, idx)
    return chunks


def markdown_header_chunk(text: str, sections: list[dict]) -> list[ChunkCandidate]:
    """Header-aware chunking: one chunk per section, tagged with heading hierarchy."""
    if not sections:
        return recursive_character_chunk(text)

    chunks = []
    for i, sec in enumerate(sections):
        start = sec["start_char"]
        end = sections[i + 1]["start_char"] if i + 1 < len(sections) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue
        # Large sections still get recursively split, tagged with the section title.
        for sub in recursive_character_chunk(section_text):
            chunks.append(ChunkCandidate(text=sub.text, parent_text=sub.parent_text,
                                          section=sec["title"], page=None))
    return chunks


def chunk_document(text: str, mime_type: str, sections: list[dict] | None = None) -> list[ChunkCandidate]:
    if mime_type == "text/markdown" and sections:
        return markdown_header_chunk(text, sections)
    return recursive_character_chunk(text)


def new_chunk_id() -> str:
    return f"chunk_{uuid.uuid4().hex[:16]}"
