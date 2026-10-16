import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify GET /api/v1/health returns HTTP 200 and expected status structure."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert data["database"] in {"connected", "disconnected", "not_configured"}
    assert "storage" in data
    assert data["storage"] in {"connected", "disconnected", "not_configured", "local_storage_ready"}


def test_openapi_docs_accessible():
    """Verify OpenAPI Swagger docs and schema are accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Document Intelligence RAG API"
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/users/me" in schema["paths"]
    assert "/api/v1/users/{user_id}" in schema["paths"]
    assert "/api/v1/documents" in schema["paths"]
    assert "/api/v1/documents/{document_id}" in schema["paths"]
    assert "/api/v1/documents/{document_id}/download" in schema["paths"]
    assert "/api/v1/conversations/{conversation_id}" in schema["paths"]
    assert "/api/v1/conversations/{conversation_id}/messages" in schema["paths"]
    assert "/api/v1/chat/query" in schema["paths"]


def test_cors_headers():
    """Verify CORS preflight response headers for allowed origins."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
