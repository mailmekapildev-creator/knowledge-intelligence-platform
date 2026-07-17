"""
LLM Gateway: the one place that talks to the model provider. Everything upstream
(query service) depends on this interface, not on an SDK directly -- this is what
makes provider swaps a config change and lets us enforce retries, timeouts, fallback
tiers, and cost logging in one place (see docs/architecture.md and
docs/failure-modes.md).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.schemas import RetrievedChunk


@dataclass
class LLMResult:
    text: str
    model_used: str
    latency_ms: float
    degraded: bool = False
    degraded_reason: str | None = None


class LLMTimeoutError(Exception):
    pass


class LLMProviderError(Exception):
    pass


def _mock_generate(system_prompt: str, messages: list[dict], chunks: list[RetrievedChunk]) -> str:
    """
    Deterministic, citation-aware mock answer -- lets the whole pipeline (including the
    evaluation harness) run without an API key. It extracts the top chunk(s), quotes
    (paraphrases) their content, and cites them, mirroring what the real model is
    instructed to do.
    """
    if not chunks:
        return "I don't have enough information in the indexed documents to answer that."

    lines = ["Based on the indexed documents:"]
    for c in chunks[:3]:
        snippet = c.chunk.text.strip().replace("\n", " ")[:500]
        tag = f"[{c.chunk.document_id}:{c.chunk.chunk_id}]"
        lines.append(f"- {snippet} {tag}")
    return "\n".join(lines)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=4))
def _call_anthropic(system_prompt: str, messages: list[dict], model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")


def generate(system_prompt: str, messages: list[dict], chunks: list[RetrievedChunk]) -> LLMResult:
    start = time.perf_counter()

    if settings.mock_mode or not settings.anthropic_api_key:
        text = _mock_generate(system_prompt, messages, chunks)
        latency_ms = (time.perf_counter() - start) * 1000
        return LLMResult(text=text, model_used="mock-model", latency_ms=latency_ms)

    try:
        text = _call_anthropic(system_prompt, messages, settings.llm_model_primary)
        latency_ms = (time.perf_counter() - start) * 1000
        return LLMResult(text=text, model_used=settings.llm_model_primary, latency_ms=latency_ms)
    except Exception as primary_error:  # noqa: BLE001 -- deliberate: any provider failure triggers fallback
        try:
            text = _call_anthropic(system_prompt, messages, settings.llm_model_fallback)
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMResult(
                text=text, model_used=settings.llm_model_fallback, latency_ms=latency_ms,
                degraded=True, degraded_reason=f"primary model failed: {primary_error}",
            )
        except Exception as fallback_error:  # noqa: BLE001
            latency_ms = (time.perf_counter() - start) * 1000
            # Graceful degradation: still return citations even if generation fails
            # entirely (see docs/failure-modes.md -- "LLM API fails").
            fallback_text = _mock_generate(system_prompt, messages, chunks)
            return LLMResult(
                text=fallback_text, model_used="degraded-fallback", latency_ms=latency_ms,
                degraded=True,
                degraded_reason=f"both model tiers failed: {fallback_error}",
            )


CITATION_PATTERN = re.compile(r"\[(doc_[a-f0-9]+):(chunk_[a-f0-9]+)\]")


def extract_cited_chunk_ids(answer_text: str) -> set[tuple[str, str]]:
    """Used by the evaluation pipeline to check that every citation in the answer
    actually corresponds to a chunk that was retrieved (a citation to a non-retrieved
    chunk is a faithfulness red flag -- see docs/observability-and-evaluation.md)."""
    return set(CITATION_PATTERN.findall(answer_text))
