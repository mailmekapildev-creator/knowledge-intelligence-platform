from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(str, Enum):
    pending = "pending"
    parsing = "parsing"
    chunking = "chunking"
    embedding = "embedding"
    indexed = "indexed"
    failed_parsing = "failed_parsing"
    failed_ocr = "failed_ocr"
    deleted = "deleted"


class Role(str, Enum):
    viewer = "viewer"
    contributor = "contributor"
    tenant_admin = "tenant_admin"
    platform_admin = "platform_admin"


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    tenant_id: str
    text: str
    parent_text: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk: Chunk
    vector_score: float
    bm25_score: float
    fused_score: float
    rerank_score: Optional[float] = None


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    snippet: str


class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    top_k: int = 6
    conversation_id: Optional[str] = None


class QueryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str
    citations: list[Citation]
    model_used: str
    latency_ms: float
    retrieved_chunk_count: int
    degraded: bool = False
    degraded_reason: Optional[str] = None


class IngestResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    message: str


class DocumentRecord(BaseModel):
    document_id: str
    tenant_id: str
    filename: str
    mime_type: str
    content_hash: str
    status: DocumentStatus
    created_at: datetime
    chunk_count: int = 0
