"""
Automated retrieval/answer-quality evaluation, RAGAS-style. Runs the query pipeline
against a golden dataset and computes faithfulness, context precision/recall, and
citation-groundedness metrics. Intended to run as a CI gate on any change to prompts,
chunking, or retrieval config (see docs/observability-and-evaluation.md).

Usage:
    python evaluation/ragas_eval.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.security import mint_dev_token  # noqa: E402
from app.db.metadata_store import metadata_store  # noqa: E402
from app.models.schemas import Role  # noqa: E402
from app.services.llm.gateway import extract_cited_chunk_ids  # noqa: E402
from app.services.llm.gateway import generate  # noqa: E402
from app.services.llm.prompt_builder import SYSTEM_PROMPT, build_prompt  # noqa: E402
from app.services.retrieval.hybrid_search import hybrid_search  # noqa: E402
from app.services.retrieval.reranker import rerank  # noqa: E402
from app.worker.tasks import process_document  # noqa: E402

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"


@dataclass
class EvalResult:
    question: str
    expected_keywords_found: bool
    context_precision: float
    context_recall_hit: bool
    groundedness: float
    citation_count: int


def _keyword_hit(answer: str, expected_keywords: list[str]) -> bool:
    lower = answer.lower()
    return any(k.lower() in lower for k in expected_keywords)


def _context_precision(chunks, expected_doc_ids: list[str]) -> float:
    if not chunks:
        return 0.0
    relevant = sum(1 for c in chunks if c.chunk.document_id in expected_doc_ids)
    return relevant / len(chunks)


def _context_recall_hit(chunks, expected_doc_ids: list[str]) -> bool:
    retrieved_docs = {c.chunk.document_id for c in chunks}
    return bool(retrieved_docs & set(expected_doc_ids))


def _groundedness(answer: str, chunks) -> float:
    """Fraction of cited chunk_ids that correspond to actually-retrieved chunks --
    a citation to a chunk that wasn't retrieved is a fabricated citation."""
    cited = extract_cited_chunk_ids(answer)
    if not cited:
        return 0.0
    retrieved_ids = {(c.chunk.document_id, c.chunk.chunk_id) for c in chunks}
    grounded = sum(1 for pair in cited if pair in retrieved_ids)
    return grounded / len(cited)


def seed_golden_corpus(tenant_id: str, docs: list[dict]) -> dict[str, str]:
    """Ingests the golden dataset's source docs synchronously and returns filename ->
    document_id so eval cases can assert against expected document ids."""
    filename_to_id = {}
    for doc in docs:
        record, _ = metadata_store.create_document(
            tenant_id=tenant_id, filename=doc["filename"], mime_type="text/plain",
            content=doc["content"].encode("utf-8"),
        )
        process_document(record.document_id, tenant_id, doc["filename"], "text/plain",
                          doc["content"].encode("utf-8"))
        filename_to_id[doc["filename"]] = record.document_id
    return filename_to_id


def run_eval() -> list[EvalResult]:
    dataset = json.loads(GOLDEN_DATASET_PATH.read_text())
    tenant_id = "eval-tenant"
    filename_to_id = seed_golden_corpus(tenant_id, dataset["documents"])

    results = []
    for case in dataset["cases"]:
        expected_doc_ids = [filename_to_id[f] for f in case["expected_source_filenames"]]

        candidates = hybrid_search(tenant_id, case["question"])
        top_chunks = rerank(case["question"], candidates)
        messages = build_prompt(case["question"], top_chunks)
        result = generate(SYSTEM_PROMPT, messages, top_chunks)

        results.append(EvalResult(
            question=case["question"],
            expected_keywords_found=_keyword_hit(result.text, case["expected_keywords"]),
            context_precision=_context_precision(top_chunks, expected_doc_ids),
            context_recall_hit=_context_recall_hit(top_chunks, expected_doc_ids),
            groundedness=_groundedness(result.text, top_chunks),
            citation_count=len(extract_cited_chunk_ids(result.text)),
        ))
    return results


def print_report(results: list[EvalResult]) -> bool:
    print(f"{'Question':<55} {'Keyword':<8} {'CtxPrec':<8} {'Recall':<7} {'Ground':<7}")
    print("-" * 90)
    passed = True
    for r in results:
        ok_keyword = "PASS" if r.expected_keywords_found else "FAIL"
        ok_recall = "PASS" if r.context_recall_hit else "FAIL"
        if not r.expected_keywords_found or not r.context_recall_hit:
            passed = False
        print(f"{r.question[:53]:<55} {ok_keyword:<8} {r.context_precision:<8.2f} "
              f"{ok_recall:<7} {r.groundedness:<7.2f}")

    avg_precision = sum(r.context_precision for r in results) / len(results)
    avg_groundedness = sum(r.groundedness for r in results) / len(results)
    recall_rate = sum(1 for r in results if r.context_recall_hit) / len(results)
    keyword_rate = sum(1 for r in results if r.expected_keywords_found) / len(results)

    print("-" * 90)
    print(f"Avg context precision: {avg_precision:.2f} | Context recall rate: {recall_rate:.2f} "
          f"| Avg groundedness: {avg_groundedness:.2f} | Keyword-match rate: {keyword_rate:.2f}")

    # CI gate thresholds -- tune per docs/observability-and-evaluation.md
    if recall_rate < 0.8 or keyword_rate < 0.8:
        print("\nEVAL FAILED: below quality threshold.")
        return False
    print("\nEVAL PASSED.")
    return True


if __name__ == "__main__":
    results = run_eval()
    ok = print_report(results)
    sys.exit(0 if ok else 1)
