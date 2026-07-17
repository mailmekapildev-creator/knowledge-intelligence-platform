"""
Metadata store abstraction. In-memory implementation for the portfolio build; shaped so
swapping in a real SQLAlchemy/Postgres-backed implementation touches only this file
(see docs/architecture.md -- Postgres is the system of record, not the vector DB).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.models.schemas import Chunk, DocumentRecord, DocumentStatus


class InMemoryMetadataStore:
    def __init__(self):
        self.documents: dict[str, DocumentRecord] = {}
        self.chunks: dict[str, Chunk] = {}
        self.content_hash_index: dict[str, str] = {}  # hash -> document_id (dedup)
        self.audit_log: list[dict] = []

    # --- documents ---
    def create_document(self, tenant_id: str, filename: str, mime_type: str,
                         content: bytes) -> tuple[DocumentRecord, bool]:
        content_hash = hashlib.sha256(content).hexdigest()
        existing_id = self.content_hash_index.get(f"{tenant_id}:{content_hash}")
        if existing_id:
            return self.documents[existing_id], True  # is_duplicate=True

        doc_id = f"doc_{uuid.uuid4().hex[:16]}"
        record = DocumentRecord(
            document_id=doc_id,
            tenant_id=tenant_id,
            filename=filename,
            mime_type=mime_type,
            content_hash=content_hash,
            status=DocumentStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        self.documents[doc_id] = record
        self.content_hash_index[f"{tenant_id}:{content_hash}"] = doc_id
        return record, False

    def update_status(self, document_id: str, status: DocumentStatus) -> None:
        if document_id in self.documents:
            self.documents[document_id].status = status

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self.documents.get(document_id)

    def list_documents(self, tenant_id: str) -> list[DocumentRecord]:
        return [d for d in self.documents.values() if d.tenant_id == tenant_id]

    def soft_delete_document(self, tenant_id: str, document_id: str) -> bool:
        doc = self.documents.get(document_id)
        if not doc or doc.tenant_id != tenant_id:
            return False
        doc.status = DocumentStatus.deleted
        return True

    # --- chunks ---
    def add_chunks(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self.chunks[c.chunk_id] = c
        if chunks:
            doc = self.documents.get(chunks[0].document_id)
            if doc:
                doc.chunk_count += len(chunks)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)

    def chunks_for_tenant(self, tenant_id: str) -> list[Chunk]:
        return [c for c in self.chunks.values() if c.tenant_id == tenant_id]

    # --- audit ---
    def log(self, event: str, **kwargs) -> None:
        self.audit_log.append({"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **kwargs})


metadata_store = InMemoryMetadataStore()
