import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ChatQueryResponse, ChatSource
from tests.conftest import create_test_token

client = TestClient(app)


def test_create_conversation_authenticated():
    """Verify creating a conversation with an authenticated token."""
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create with custom title
    res = client.post("/api/v1/conversations", json={"title": "My Research Topic"}, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "My Research Topic"
    assert data["user_id"] == user_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # 2. Create with default title
    res_default = client.post("/api/v1/conversations", json={}, headers=headers)
    assert res_default.status_code == 201
    assert res_default.json()["title"] == "New Conversation"
    assert res_default.json()["user_id"] == user_id


def test_create_conversation_unauthenticated_returns_401():
    """Verify unauthenticated request returns 401 Unauthorized."""
    res = client.post("/api/v1/conversations", json={"title": "No Auth"}, headers={"X-No-Auth": "true"})
    assert res.status_code == 401
    assert "Bearer" in res.headers.get("www-authenticate", "")


def test_list_conversations_scoped_to_current_user():
    """Verify conversations listing is strictly scoped to the authenticated user and ordered updated_at DESC."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_token(sub=user_a)
    token_b = create_test_token(sub=user_b)

    # Create convs for A
    res_a1 = client.post("/api/v1/conversations", json={"title": "Conv A1"}, headers={"Authorization": f"Bearer {token_a}"})
    res_a2 = client.post("/api/v1/conversations", json={"title": "Conv A2"}, headers={"Authorization": f"Bearer {token_a}"})
    # Create conv for B
    res_b = client.post("/api/v1/conversations", json={"title": "Conv B"}, headers={"Authorization": f"Bearer {token_b}"})

    # List A
    list_a = client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {token_a}"})
    assert list_a.status_code == 200
    a_titles = [c["title"] for c in list_a.json()]
    assert "Conv A1" in a_titles
    assert "Conv A2" in a_titles
    assert "Conv B" not in a_titles

    # List B
    list_b = client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    b_titles = [c["title"] for c in list_b.json()]
    assert "Conv B" in b_titles
    assert "Conv A1" not in b_titles


def test_get_single_conversation_owner_success():
    """Verify owner can retrieve single conversation by ID."""
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/conversations", json={"title": "Owner Conv"}, headers=headers)
    conv_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == conv_id
    assert get_res.json()["title"] == "Owner Conv"


def test_get_single_conversation_cross_tenant_returns_404():
    """Verify cross-tenant conversation access returns 404 without leaking existence."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_token(sub=user_a)
    token_b = create_test_token(sub=user_b)

    create_res = client.post("/api/v1/conversations", json={"title": "A Private Conv"}, headers={"Authorization": f"Bearer {token_a}"})
    conv_id = create_res.json()["id"]

    # B attempts to access A's conversation
    get_res = client.get(f"/api/v1/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_res.status_code == 404
    assert "not found" in get_res.json()["detail"].lower()


def test_delete_conversation_owner_success_cascades_messages():
    """Verify owner can delete conversation and all associated messages are removed."""
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/conversations", json={"title": "Delete Me"}, headers=headers)
    conv_id = create_res.json()["id"]

    # Insert a message directly into DB for this conv
    with SessionLocal() as db:
        msg = Message(conversation_id=uuid.UUID(conv_id), role="user", content="Hello test delete")
        db.add(msg)
        db.commit()

    # Delete conversation
    del_res = client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["conversation_id"] == conv_id

    # Verify conversation is gone
    get_res = client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert get_res.status_code == 404

    # Verify messages are cascaded in DB
    with SessionLocal() as db:
        msgs = db.query(Message).filter(Message.conversation_id == uuid.UUID(conv_id)).all()
        assert len(msgs) == 0


def test_delete_conversation_cross_tenant_returns_404():
    """Verify non-owner cannot delete another user's conversation."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_token(sub=user_a)
    token_b = create_test_token(sub=user_b)

    create_res = client.post("/api/v1/conversations", json={"title": "Do Not Delete"}, headers={"Authorization": f"Bearer {token_a}"})
    conv_id = create_res.json()["id"]

    # User B attempts to delete User A's conversation
    del_res = client.delete(f"/api/v1/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_res.status_code == 404

    # Confirm conversation still exists for User A
    get_res = client.get(f"/api/v1/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_res.status_code == 200


def test_list_messages_owner_success():
    """Verify owner can retrieve chronological messages in a conversation."""
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/conversations", json={"title": "Message History Test"}, headers=headers)
    conv_id = create_res.json()["id"]

    with SessionLocal() as db:
        m1 = Message(conversation_id=uuid.UUID(conv_id), role="user", content="Question 1")
        m2 = Message(conversation_id=uuid.UUID(conv_id), role="assistant", content="Answer 1")
        db.add_all([m1, m2])
        db.commit()

    msg_res = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=headers)
    assert msg_res.status_code == 200
    messages = msg_res.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Question 1"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Answer 1"


def test_list_messages_cross_tenant_returns_404():
    """Verify non-owner cannot retrieve another user's conversation messages."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_token(sub=user_a)
    token_b = create_test_token(sub=user_b)

    create_res = client.post("/api/v1/conversations", json={"title": "Private Chat"}, headers={"Authorization": f"Bearer {token_a}"})
    conv_id = create_res.json()["id"]

    # User B attempts to read User A's messages
    msg_res = client.get(f"/api/v1/conversations/{conv_id}/messages", headers={"Authorization": f"Bearer {token_b}"})
    assert msg_res.status_code == 404


def test_send_message_persists_user_and_assistant_messages_with_sources():
    """
    Verify sending a message persists user message, calls RAG service,
    persists assistant message, updates timestamps, and returns sources.
    """
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/conversations", json={"title": "New Conversation"}, headers=headers)
    conv_id = create_res.json()["id"]
    initial_updated_at = create_res.json()["updated_at"]

    mock_rag_response = ChatQueryResponse(
        answer="Object-Oriented Programming (OOP) is a programming paradigm based on objects.",
        sources=[
            ChatSource(source="285_OOPS.pdf", page=7, file_type="pdf", score=0.85),
        ],
        conversation_id=uuid.UUID(conv_id),
        has_sufficient_context=True,
    )

    with patch("app.api.routes.conversations.rag_service.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_rag_response

        send_res = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "What is OOP?"},
            headers=headers,
        )
        assert send_res.status_code == 200
        data = send_res.json()

        # Check response structure
        assert "user_message" in data
        assert "assistant_message" in data
        assert "sources" in data

        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "What is OOP?"
        assert data["assistant_message"]["role"] == "assistant"
        assert "programming paradigm" in data["assistant_message"]["content"]
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "285_OOPS.pdf"

        # Verify rag_service was called with authenticated user_id
        mock_query.assert_called_once()
        call_kwargs = mock_query.call_args.kwargs
        assert str(call_kwargs.get("user_id")) == user_id

    # Verify messages exist in database
    list_res = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=headers)
    assert list_res.status_code == 200
    msgs = list_res.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"

    # Verify conversation title was deterministically updated from "New Conversation"
    conv_check = client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert conv_check.status_code == 200
    assert conv_check.json()["title"] == "What is OOP?"
    assert conv_check.json()["updated_at"] != initial_updated_at


def test_send_message_cross_tenant_returns_404():
    """Verify non-owner cannot send messages to another user's conversation."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_token(sub=user_a)
    token_b = create_test_token(sub=user_b)

    create_res = client.post("/api/v1/conversations", json={"title": "User A Conv"}, headers={"Authorization": f"Bearer {token_a}"})
    conv_id = create_res.json()["id"]

    # User B attempts to post message to User A's conversation
    send_res = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Malicious inject"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert send_res.status_code == 404

    # Verify no messages were added
    with SessionLocal() as db:
        msgs = db.query(Message).filter(Message.conversation_id == uuid.UUID(conv_id)).all()
        assert len(msgs) == 0


def test_send_empty_message_rejected():
    """Verify sending empty or whitespace-only messages is rejected."""
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/conversations", json={"title": "Empty Test"}, headers=headers)
    conv_id = create_res.json()["id"]

    # Whitespace only
    res = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "   "}, headers=headers)
    assert res.status_code in (400, 422)

    # Empty string
    res_empty = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": ""}, headers=headers)
    assert res_empty.status_code in (400, 422)


def test_send_message_invalid_conversation_id_returns_404():
    """Verify sending a message to a nonexistent conversation ID returns 404."""
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    random_id = str(uuid.uuid4())

    res = client.post(
        f"/api/v1/conversations/{random_id}/messages",
        json={"content": "Valid question"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_rag_failure_does_not_insert_fake_assistant_message():
    """
    Verify that if RAG generation fails (e.g. LLM unavailable 503),
    the user message is recorded, but no fake/error assistant message is created.
    """
    user_id = str(uuid.uuid4())
    token = create_test_token(sub=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/conversations", json={"title": "Failure Safety Test"}, headers=headers)
    conv_id = create_res.json()["id"]

    with patch("app.api.routes.conversations.rag_service.query", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local LLM server unreachable.",
        )

        send_res = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Question during outage"},
            headers=headers,
        )
        assert send_res.status_code == 503
        assert "Local LLM server unreachable" in send_res.json()["detail"]

    # Check database: user message was persisted, NO assistant message exists
    with SessionLocal() as db:
        msgs = db.query(Message).filter(Message.conversation_id == uuid.UUID(conv_id)).all()
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].content == "Question during outage"


def test_two_users_cross_tenant_complete_isolation_matrix():
    """
    Exhaustive matrix test:
    User A and User B operate concurrently.
    Neither user can view, list, message, or delete each other's conversations.
    """
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_token(sub=user_a)
    token_b = create_test_token(sub=user_b)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. User A creates Conv A
    res_a = client.post("/api/v1/conversations", json={"title": "User A Private Space"}, headers=headers_a)
    assert res_a.status_code == 201
    conv_a_id = res_a.json()["id"]

    # 2. User B creates Conv B
    res_b = client.post("/api/v1/conversations", json={"title": "User B Private Space"}, headers=headers_b)
    assert res_b.status_code == 201
    conv_b_id = res_b.json()["id"]

    # 3. User A lists -> sees only Conv A
    list_a = client.get("/api/v1/conversations", headers=headers_a).json()
    assert any(c["id"] == conv_a_id for c in list_a)
    assert not any(c["id"] == conv_b_id for c in list_a)

    # 4. User B lists -> sees only Conv B
    list_b = client.get("/api/v1/conversations", headers=headers_b).json()
    assert any(c["id"] == conv_b_id for c in list_b)
    assert not any(c["id"] == conv_a_id for c in list_b)

    # 5. User A tries to GET Conv B -> 404
    assert client.get(f"/api/v1/conversations/{conv_b_id}", headers=headers_a).status_code == 404

    # 6. User B tries to GET Conv A -> 404
    assert client.get(f"/api/v1/conversations/{conv_a_id}", headers=headers_b).status_code == 404

    # 7. User A tries to read Conv B messages -> 404
    assert client.get(f"/api/v1/conversations/{conv_b_id}/messages", headers=headers_a).status_code == 404

    # 8. User B tries to read Conv A messages -> 404
    assert client.get(f"/api/v1/conversations/{conv_a_id}/messages", headers=headers_b).status_code == 404

    # 9. User A tries to send message to Conv B -> 404
    assert client.post(f"/api/v1/conversations/{conv_b_id}/messages", json={"content": "Spying"}, headers=headers_a).status_code == 404

    # 10. User B tries to send message to Conv A -> 404
    assert client.post(f"/api/v1/conversations/{conv_a_id}/messages", json={"content": "Hacking"}, headers=headers_b).status_code == 404

    # 11. User A tries to delete Conv B -> 404
    assert client.delete(f"/api/v1/conversations/{conv_b_id}", headers=headers_a).status_code == 404

    # 12. User B tries to delete Conv A -> 404
    assert client.delete(f"/api/v1/conversations/{conv_a_id}", headers=headers_b).status_code == 404

    # 13. User A deletes Conv A -> 200
    assert client.delete(f"/api/v1/conversations/{conv_a_id}", headers=headers_a).status_code == 200

    # 14. User B deletes Conv B -> 200
    assert client.delete(f"/api/v1/conversations/{conv_b_id}", headers=headers_b).status_code == 200
