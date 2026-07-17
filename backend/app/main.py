from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, ingest, query
from app.config import settings

app = FastAPI(
    title="Knowledge Intelligence Platform",
    description="Enterprise multi-tenant RAG platform -- see /docs for the API console, "
                 "and the repo's docs/ folder for the full architecture write-up.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened to known frontend origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok", "mock_mode": settings.mock_mode}


@app.get("/")
async def root():
    return {
        "service": "knowledge-intelligence-platform",
        "mock_mode": settings.mock_mode,
        "docs": "/docs",
        "get_a_dev_token": "POST /api/v1/admin/dev-token?user_id=alice&tenant_id=acme",
    }
