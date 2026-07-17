from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile

from app.core.security import AuthContext, get_auth_context
from app.db.metadata_store import metadata_store
from app.models.schemas import DocumentRecord, DocumentStatus, IngestResponse, Role
from app.worker.tasks import delete_document, process_document

router = APIRouter(prefix="/api/v1/documents", tags=["ingestion"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB cap -- see docs/security.md (file validation)
ALLOWED_EXTENSIONS = {"txt", "md", "markdown", "html", "htm", "csv", "pdf", "docx"}


@router.post("", response_model=IngestResponse)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    ctx: AuthContext = Depends(get_auth_context),
):
    ext = file.filename.lower().rsplit(".", 1)[-1] if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"unsupported file type: .{ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 25MB limit")

    record, is_duplicate = metadata_store.create_document(
        tenant_id=ctx.tenant_id, filename=file.filename, mime_type=file.content_type or "application/octet-stream",
        content=content,
    )

    if is_duplicate:
        return IngestResponse(document_id=record.document_id, status=record.status,
                               message="duplicate content detected -- linked to existing document, not re-ingested")

    # Async by design: the request returns immediately, ingestion happens in the
    # background (in production: enqueued to a broker) -- see docs/architecture.md.
    background_tasks.add_task(
        process_document, record.document_id, ctx.tenant_id, file.filename,
        file.content_type or "application/octet-stream", content,
    )

    return IngestResponse(document_id=record.document_id, status=DocumentStatus.pending,
                           message="accepted for processing")


@router.get("", response_model=list[DocumentRecord])
async def list_documents(ctx: AuthContext = Depends(get_auth_context)):
    return metadata_store.list_documents(ctx.tenant_id)


@router.get("/{document_id}", response_model=DocumentRecord)
async def get_document(document_id: str, ctx: AuthContext = Depends(get_auth_context)):
    doc = metadata_store.get_document(document_id)
    if not doc or doc.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.delete("/{document_id}")
async def delete_document_route(document_id: str, ctx: AuthContext = Depends(get_auth_context)):
    if ctx.role.value not in (Role.tenant_admin.value, Role.platform_admin.value):
        raise HTTPException(status_code=403, detail="requires tenant_admin or platform_admin")
    ok = delete_document(ctx.tenant_id, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="document not found")
    return {"status": "deleted", "document_id": document_id}
