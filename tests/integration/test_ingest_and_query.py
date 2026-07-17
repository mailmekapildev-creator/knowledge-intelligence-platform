"""
Integration test: full ingestion -> retrieval -> query round trip, using MOCK_MODE so
it's deterministic, free, and fast (no external calls) -- see docs/observability-and-
evaluation.md ("Testing pyramid").
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get_token(tenant_id: str = "test-tenant", role: str = "tenant_admin") -> str:
    resp = client.post(
        "/api/v1/admin/dev-token",
        params={"user_id": "test-user", "tenant_id": tenant_id, "role": role},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_full_ingest_and_query_round_trip():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    content = (
        b"Vacation Policy\n\n"
        b"Full-time employees accrue 15 days of paid vacation per year.\n"
        b"Unused vacation days roll over up to a maximum of 5 days into the next year."
    )
    upload = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("vacation.txt", content, "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    doc_status = client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert doc_status.status_code == 200
    assert doc_status.json()["status"] == "indexed"

    query_resp = client.post(
        "/api/v1/query",
        headers=headers,
        json={"query": "How many vacation days do employees accrue?", "tenant_id": "test-tenant"},
    )
    assert query_resp.status_code == 200
    body = query_resp.json()
    assert body["retrieved_chunk_count"] >= 1
    assert len(body["citations"]) >= 1
    assert document_id in body["citations"][0]["document_id"]


def test_cross_tenant_isolation():
    """A user from tenant A must never see tenant B's documents (docs/security.md)."""
    token_a = _get_token(tenant_id="tenant-a")
    token_b = _get_token(tenant_id="tenant-b")

    client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("secret.txt", b"Tenant A confidential merger plan details.", "text/plain")},
    )

    query_resp = client.post(
        "/api/v1/query",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"query": "merger plan", "tenant_id": "tenant-b"},
    )
    assert query_resp.status_code == 200
    assert query_resp.json()["retrieved_chunk_count"] == 0


def test_unsupported_file_type_rejected():
    token = _get_token()
    resp = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malware.exe", b"binary content", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_query_without_auth_is_rejected():
    resp = client.post("/api/v1/query", json={"query": "anything", "tenant_id": "acme"})
    assert resp.status_code == 401
