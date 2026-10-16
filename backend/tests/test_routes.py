import uuid
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.services.rag_service import rag_service

client = TestClient(app)


def test_chat_query_request_validation():
    """Verify POST /api/v1/chat/query validates required fields."""
    # Empty question
    res = client.post(
        "/api/v1/chat/query",
        json={"question": "", "user_id": str(uuid.uuid4())},
    )
    assert res.status_code == 422


def test_chat_query_success_with_mock():
    """Verify chat query returns answer and structured sources when RAG engine generates response."""
    test_uid = str(uuid.uuid4())
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [
        {
            "text": "Encapsulation is wrapping data and methods into a single unit.",
            "source": "oops_notes.pdf",
            "page": 9,
            "file_type": "pdf",
            "rerank_score": 0.88,
        }
    ]
    mock_generator = MagicMock()
    mock_generator.generate.return_value = "Encapsulation wraps data and methods into a single unit."

    orig_retriever = rag_service._retriever
    orig_generator = rag_service._generator
    try:
        rag_service._retriever = mock_retriever
        rag_service._generator = mock_generator

        response = client.post(
            "/api/v1/chat/query",
            json={
                "user_id": test_uid,
                "question": "What is encapsulation?",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Encapsulation wraps data and methods into a single unit."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "oops_notes.pdf"
        assert data["sources"][0]["page"] == 9
        assert data["has_sufficient_context"] is True
    finally:
        rag_service._retriever = orig_retriever
        rag_service._generator = orig_generator


def test_chat_query_missing_context_handling():
    """Verify chat query handles missing document context properly."""
    test_uid = str(uuid.uuid4())
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = []  # No candidates above threshold

    orig_retriever = rag_service._retriever
    try:
        rag_service._retriever = mock_retriever

        response = client.post(
            "/api/v1/chat/query",
            json={
                "user_id": test_uid,
                "question": "What is the culinary history of chocolate in ancient Aztec civilization?",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "The provided documents do not contain enough information to answer this question." in data["answer"]
        assert data["sources"] == []
        assert data["has_sufficient_context"] is False
    finally:
        rag_service._retriever = orig_retriever


def test_chat_query_llm_unavailable_handling():
    """Verify chat query converts LLM server connection failure into clean 503 error."""
    test_uid = str(uuid.uuid4())
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [
        {"text": "Sample text", "source": "test.txt", "rerank_score": 0.75}
    ]
    mock_generator = MagicMock()
    mock_generator.generate.return_value = "[ERROR] Unable to generate an answer. Please make sure the local LLM server is running."

    orig_retriever = rag_service._retriever
    orig_generator = rag_service._generator
    try:
        rag_service._retriever = mock_retriever
        rag_service._generator = mock_generator

        response = client.post(
            "/api/v1/chat/query",
            json={
                "user_id": test_uid,
                "question": "What is an operating system?",
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert "Local LLM server (Qwen) is currently unreachable" in data["detail"]
    finally:
        rag_service._retriever = orig_retriever
        rag_service._generator = orig_generator


def test_unconfigured_db_routes_return_503():
    """When database session dependency yields None, routes return 503."""
    app.dependency_overrides[get_db] = lambda: None
    try:
        test_uid = str(uuid.uuid4())
        user_res = client.get(f"/api/v1/users/{test_uid}")
        assert user_res.status_code == 503

        doc_res = client.get("/api/v1/documents")
        assert doc_res.status_code == 503

        conv_res = client.get(f"/api/v1/conversations/{test_uid}")
        assert conv_res.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_configured_db_routes_query_execution():
    """When database is connected, queries execute properly (404 for inaccessible user, 200 for lists)."""
    test_uid = str(uuid.uuid4())
    other_uid = str(uuid.uuid4())
    # Request other user's profile with test_uid's token -> 404
    user_res = client.get(f"/api/v1/users/{other_uid}", params={"user_id": test_uid})
    assert user_res.status_code == 404

    doc_res = client.get("/api/v1/documents")
    assert doc_res.status_code == 200
    assert isinstance(doc_res.json(), list)

    conv_res = client.get("/api/v1/conversations")
    assert conv_res.status_code == 200
    assert isinstance(conv_res.json(), list)
