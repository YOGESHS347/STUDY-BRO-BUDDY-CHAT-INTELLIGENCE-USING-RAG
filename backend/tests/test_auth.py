import logging
import time
import uuid
from typing import Optional
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.auth import AuthenticatedUser, get_current_user, jwt_verifier
from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.user import User

client = TestClient(app)

# Generate an in-memory EC key pair (P-256 / ES256) for cryptographic testing
_test_private_key = ec.generate_private_key(ec.SECP256R1())
_test_public_key = _test_private_key.public_key()
_alt_private_key = ec.generate_private_key(ec.SECP256R1())
_test_kid = "test-ec-kid-001"


def create_test_jwt(
    sub: str,
    email: str = "test@example.com",
    exp_offset: int = 3600,
    signing_key=_test_private_key,
    kid: str = _test_kid,
    aud: str = "authenticated",
    iss: Optional[str] = None,
) -> str:
    """Creates a cryptographically signed ES256 JWT for unit testing."""
    payload = {
        "sub": sub,
        "email": email,
        "role": "authenticated",
        "aud": aud,
        "iss": iss or f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1",
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, signing_key, algorithm="ES256", headers={"kid": kid})


def mock_signing_key_getter(token: str):
    """Mocks PyJWKClient to return the matching test public key."""
    mock_jwk = MagicMock()
    mock_jwk.key = _test_public_key
    mock_jwk.key_id = _test_kid
    return mock_jwk


# ============================================================
# 1. JWT Cryptographic Verification & Error Handling Tests
# ============================================================

def test_missing_authorization_header_returns_401():
    """Verify protected endpoints return HTTP 401 when Authorization header is omitted."""
    res_upload = client.post("/api/v1/documents/upload")
    assert res_upload.status_code == 401
    assert "Missing Authorization header" in res_upload.json()["detail"]

    res_docs = client.get("/api/v1/documents")
    assert res_docs.status_code == 401

    res_me = client.get("/api/v1/users/me")
    assert res_me.status_code == 401

    res_chat = client.post("/api/v1/chat/query", json={"question": "What is OOP?"})
    assert res_chat.status_code == 401


def test_invalid_scheme_returns_401():
    """Verify non-Bearer scheme (e.g. Basic, Token) is rejected with HTTP 401."""
    headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    res = client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 401
    assert "Invalid authentication scheme" in res.json()["detail"]


def test_malformed_jwt_returns_401():
    """Verify invalid/malformed JWT string returns HTTP 401."""
    headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
    res = client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 401
    assert "Invalid authentication token" in res.json()["detail"]


def test_expired_jwt_returns_401():
    """Verify expired token is rejected with HTTP 401."""
    uid = str(uuid.uuid4())
    expired_token = create_test_jwt(sub=uid, exp_offset=-100)
    headers = {"Authorization": f"Bearer {expired_token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        res = client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 401
        assert "expired" in res.json()["detail"].lower()


def test_invalid_signature_returns_401():
    """Verify token signed with an unknown/untrusted key is rejected."""
    uid = str(uuid.uuid4())
    # Sign with untrusted alternate key
    bad_token = create_test_jwt(sub=uid, signing_key=_alt_private_key)
    headers = {"Authorization": f"Bearer {bad_token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        res = client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 401
        assert "Invalid authentication token" in res.json()["detail"]


def test_invalid_issuer_returns_401():
    """Verify token with mismatched issuer is rejected."""
    uid = str(uuid.uuid4())
    bad_iss_token = create_test_jwt(sub=uid, iss="https://rogue-supabase.evil.com/auth/v1")
    headers = {"Authorization": f"Bearer {bad_iss_token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        res = client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 401
        assert "Invalid token issuer" in res.json()["detail"]


def test_valid_jwt_extracts_authenticated_user():
    """Verify valid token returns AuthenticatedUser with correct UUID and email."""
    uid = str(uuid.uuid4())
    token = create_test_jwt(sub=uid, email="alice@test.com")

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        auth_user = jwt_verifier.verify_token(token)
        assert auth_user.id == uuid.UUID(uid)
        assert auth_user.email == "alice@test.com"
        assert auth_user.role == "authenticated"


# ============================================================
# 2. Endpoint Protection & /users/me Tests
# ============================================================

def test_users_me_returns_authenticated_profile():
    """Verify GET /api/v1/users/me returns authenticated caller's profile."""
    uid = str(uuid.uuid4())
    unique_email = f"test_me_{uuid.uuid4().hex[:6]}@user.com"
    token = create_test_jwt(sub=uid, email=unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        res = client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == uid
        assert data["email"] == unique_email
        assert "password_hash" not in data


def test_users_cannot_access_other_user_profile():
    """Verify GET /api/v1/users/{other_user_id} returns 404."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_jwt(sub=user_a, email="user_a@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        # User A tries to view User B's profile
        res = client.get(f"/api/v1/users/{user_b}", headers=headers_a)
        assert res.status_code == 404


# ============================================================
# 3. Document Tenant Isolation & Client user_id Ignored
# ============================================================

def test_document_upload_derives_user_from_jwt():
    """
    Verify upload binds document to the authenticated token identity,
    and rejects client-supplied user_id if it attempts identity spoofing.
    """
    auth_uid = str(uuid.uuid4())
    spoofed_uid = str(uuid.uuid4())
    token = create_test_jwt(sub=auth_uid, email=f"uploader_{uuid.uuid4().hex[:6]}@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter), \
         patch("app.services.ingestion_service.ingestion_service.process_document_job"):
        # 1. Attempt upload with conflicting user_id -> 403 Forbidden
        files = {"file": ("notes.txt", b"Secret research", "text/plain")}
        data_spoofed = {"user_id": spoofed_uid}
        res_spoofed = client.post("/api/v1/documents/upload", files=files, data=data_spoofed, headers=headers)
        assert res_spoofed.status_code == 403
        assert "conflicts with authenticated" in res_spoofed.json()["detail"]

        # 2. Legitimate upload with token only (no user_id in form) -> 202 Accepted
        files_ok = {"file": ("notes.txt", b"Secret research", "text/plain")}
        res_ok = client.post("/api/v1/documents/upload", files=files_ok, headers=headers)
        assert res_ok.status_code == 202
        doc_id = res_ok.json()["document_id"]

        # 3. Verify DB record was bound to auth_uid
        db = SessionLocal()
        doc = db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        assert str(doc.user_id) == auth_uid
        assert doc.storage_path.startswith(auth_uid)
        db.close()

        # Clean up
        client.delete(f"/api/v1/documents/{doc_id}", headers=headers)


def test_cross_tenant_document_isolation():
    """
    Verify complete multi-tenant boundary:
    USER_A cannot list, download, inspect, or delete USER_B's documents.
    """
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    token_a = create_test_jwt(sub=user_a, email=f"user_a_{uuid.uuid4().hex[:6]}@test.com")
    token_b = create_test_jwt(sub=user_b, email=f"user_b_{uuid.uuid4().hex[:6]}@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter), \
         patch("app.services.ingestion_service.ingestion_service.process_document_job"):
        # User A uploads a document
        files_a = {"file": ("user_a_doc.txt", b"Confidential A data", "text/plain")}
        up_a = client.post("/api/v1/documents/upload", files=files_a, headers=headers_a)
        assert up_a.status_code == 202
        doc_a_id = up_a.json()["document_id"]
        job_a_id = up_a.json()["job_id"]

        try:
            # 1. User B lists documents -> does not see doc_a
            list_b = client.get("/api/v1/documents", headers=headers_b)
            assert list_b.status_code == 200
            doc_ids_b = [d["id"] for d in list_b.json()]
            assert doc_a_id not in doc_ids_b

            # 2. User B tries to get doc_a -> 404
            get_b = client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
            assert get_b.status_code == 404

            # 3. User B tries to download doc_a -> 404
            dl_b = client.get(f"/api/v1/documents/{doc_a_id}/download", headers=headers_b)
            assert dl_b.status_code == 404

            # 4. User B tries to inspect User A's ingestion job -> 404
            job_b = client.get(f"/api/v1/ingestion/{job_a_id}", headers=headers_b)
            assert job_b.status_code == 404

            # 5. User B tries to delete doc_a -> 404
            del_b = client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
            assert del_b.status_code == 404

            # 6. User A can download their own document -> 200
            dl_a = client.get(f"/api/v1/documents/{doc_a_id}/download", headers=headers_a)
            assert dl_a.status_code == 200
            assert dl_a.content == b"Confidential A data"

        finally:
            client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_a)


def test_chat_query_uses_authenticated_user_identity():
    """Verify chat query ignores client user_id and scopes retrieval to authenticated token identity."""
    auth_user = str(uuid.uuid4())
    fake_user = str(uuid.uuid4())
    token = create_test_jwt(sub=auth_user, email="chat_user@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        with patch("app.services.rag_service.rag_service.query") as mock_rag_query:
            from app.schemas.chat import ChatQueryResponse
            mock_rag_query.return_value = ChatQueryResponse(
                answer="Test grounded answer.",
                sources=[],
                has_sufficient_context=True,
            )

            # Send request containing a fake user_id in the JSON body
            body = {
                "question": "Explain multi-tenant architecture",
                "user_id": fake_user,
            }
            res = client.post("/api/v1/chat/query", json=body, headers=headers)
            assert res.status_code == 200

            # Verify rag_service.query was called with the authenticated user UUID, NOT fake_user
            assert mock_rag_query.called
            called_args, called_kwargs = mock_rag_query.call_args
            assert called_kwargs["user_id"] == uuid.UUID(auth_user)


def test_no_secrets_or_jwts_in_responses_or_logs(caplog):
    """Verify secret keys and access tokens are never leaked into API responses or log entries."""
    caplog.set_level(logging.DEBUG)
    uid = str(uuid.uuid4())
    token = create_test_jwt(sub=uid)
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_signing_key_getter):
        res = client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 200

        # Response must not contain secrets
        res_str = str(res.json())
        if settings.SUPABASE_SECRET_KEY:
            assert settings.SUPABASE_SECRET_KEY not in res_str
        assert "service_role" not in res_str
        assert token not in res_str

        # Log records must not contain the JWT token or secret key
        for record in caplog.records:
            msg = record.getMessage()
            assert token not in msg
            if settings.SUPABASE_SECRET_KEY:
                assert settings.SUPABASE_SECRET_KEY not in msg
