"""
Ingestion pipeline: parse -> chunk -> embed -> index. In production this runs in a
worker pool consuming a queue (SQS/RabbitMQ), scaled independently from the API tier
on queue depth (see docs/architecture.md, docs/cost-and-scalability.md). For the
portfolio build it runs as a FastAPI BackgroundTask so the whole flow is exercisable
without standing up a broker -- the function boundary is identical either way, which is
the point: swapping "called from a BackgroundTask" for "called from a queue consumer"
does not change this code.
"""
from __future__ import annotations

from app.db.metadata_store import metadata_store
from app.db.vector_store import vector_store
from app.models.schemas import Chunk, DocumentStatus
from app.services.embedding.embedder import embed_batch
from app.services.ingestion.chunking import chunk_document, new_chunk_id
from app.services.ingestion.parsers import ParsingError, UnsupportedFormatError, parse_document


def process_document(document_id: str, tenant_id: str, filename: str, mime_type: str, content: bytes) -> None:
    metadata_store.log("ingestion_started", document_id=document_id, tenant_id=tenant_id)

    try:
        metadata_store.update_status(document_id, DocumentStatus.parsing)
        parsed = parse_document(filename, content, mime_type)
    except UnsupportedFormatError as e:
        metadata_store.update_status(document_id, DocumentStatus.failed_parsing)
        metadata_store.log("ingestion_failed", document_id=document_id, reason=str(e))
        return
    except ParsingError as e:
        # OCR-eligible failure path is distinguished so the admin dashboard can route it
        # differently (see docs/failure-modes.md -- "OCR fails on a document").
        status = DocumentStatus.failed_ocr if "scanned" in e.reason else DocumentStatus.failed_parsing
        metadata_store.update_status(document_id, status)
        metadata_store.log("ingestion_failed", document_id=document_id, reason=e.reason)
        return

    metadata_store.update_status(document_id, DocumentStatus.chunking)
    candidates = chunk_document(parsed.text, parsed.mime_type, parsed.sections)
    if not candidates:
        metadata_store.update_status(document_id, DocumentStatus.failed_parsing)
        metadata_store.log("ingestion_failed", document_id=document_id, reason="no chunks produced")
        return

    metadata_store.update_status(document_id, DocumentStatus.embedding)
    texts = [c.text for c in candidates]
    vectors = embed_batch(texts)

    chunks: list[Chunk] = []
    for candidate, vector in zip(candidates, vectors):
        cid = new_chunk_id()
        chunk = Chunk(
            chunk_id=cid,
            document_id=document_id,
            tenant_id=tenant_id,
            text=candidate.text,
            parent_text=candidate.parent_text,
            section=candidate.section,
            metadata={"document_id": document_id, "filename": filename},
        )
        chunks.append(chunk)
        vector_store.upsert(tenant_id, cid, vector,
                             metadata={"document_id": document_id, "filename": filename})

    metadata_store.add_chunks(chunks)
    metadata_store.update_status(document_id, DocumentStatus.indexed)
    metadata_store.log("ingestion_completed", document_id=document_id, chunk_count=len(chunks))


def delete_document(tenant_id: str, document_id: str) -> bool:
    """Two-phase delete per ADR-003: metadata marked deleted immediately (invisible to
    queries right away), vector cleanup can be async in a real deployment -- done
    synchronously here since the in-memory store makes it cheap."""
    ok = metadata_store.soft_delete_document(tenant_id, document_id)
    if ok:
        vector_store.delete_document(tenant_id, document_id)
        metadata_store.log("document_deleted", document_id=document_id, tenant_id=tenant_id)
    return ok
