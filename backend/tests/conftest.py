import time
import urllib.parse
import uuid
from typing import Optional
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.auth import jwt_verifier
from app.core.config import settings

_test_private_key = ec.generate_private_key(ec.SECP256R1())
_test_public_key = _test_private_key.public_key()
_test_kid = "conftest-ec-kid-001"


def create_test_token(sub: str, email: Optional[str] = None) -> str:
    payload = {
        "sub": sub,
        "email": email or f"user_{sub[:8]}@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iss": f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, _test_private_key, algorithm="ES256", headers={"kid": _test_kid})


def mock_conftest_key_getter(token: str):
    mock_jwk = MagicMock()
    mock_jwk.key = _test_public_key
    mock_jwk.key_id = _test_kid
    return mock_jwk


@pytest.fixture(autouse=True)
def auto_bearer_token(request, monkeypatch):
    """
    Automatically attaches a cryptographically valid ES256 Bearer JWT
    for legacy tests outside test_auth.py.
    Extracts the test's target user_id from query params, form data, json body,
    or path segments so existing business-logic and pipeline tests seamlessly
    run through the real authentication verification pipeline.
    """
    if "test_auth" in request.node.nodeid:
        yield
        return

    orig_request = TestClient.request

    def wrapped_request(self, method, url, *args, **kwargs):
        headers = kwargs.get("headers")
        if headers is None:
            headers = {}
            kwargs["headers"] = headers

        if headers.pop("X-No-Auth", None) or headers.pop("x-no-auth", None):
            return orig_request(self, method, url, *args, **kwargs)

        # If Authorization header is not set, synthesize one for legacy tests
        if "Authorization" not in headers and "authorization" not in headers:
            uid = None

            # 1. Check query params dict
            params = kwargs.get("params")
            if params and isinstance(params, dict) and "user_id" in params:
                uid = str(params["user_id"])

            # 2. Check URL query string
            if not uid and "user_id=" in str(url):
                parsed = urllib.parse.urlparse(str(url))
                q = urllib.parse.parse_qs(parsed.query)
                if "user_id" in q:
                    uid = q["user_id"][0]

            # 3. Check multipart/form data
            if not uid:
                data = kwargs.get("data")
                if data and isinstance(data, dict) and "user_id" in data:
                    uid = str(data["user_id"])

            # 4. Check json body
            if not uid:
                json_data = kwargs.get("json")
                if json_data and isinstance(json_data, dict) and "user_id" in json_data and json_data["user_id"]:
                    uid = str(json_data["user_id"])

            # 5. Check URL path for UUID
            if not uid:
                parsed_path = urllib.parse.urlparse(str(url)).path.rstrip("/")
                last_seg = parsed_path.split("/")[-1]
                try:
                    uuid.UUID(last_seg)
                    uid = last_seg
                except Exception:
                    pass

            if not uid:
                uid = "00000000-0000-0000-0000-000000000001"

            headers["Authorization"] = f"Bearer {create_test_token(sub=uid)}"

        return orig_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(TestClient, "request", wrapped_request)
    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_conftest_key_getter):
        yield
