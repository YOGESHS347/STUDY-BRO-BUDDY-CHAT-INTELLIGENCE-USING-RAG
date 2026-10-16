import logging
from typing import Any, Dict, Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

# OpenAPI Bearer security scheme definition for Swagger UI
security = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Internal representation of a verified Supabase Auth user identity."""
    id: UUID
    email: Optional[str] = None
    role: Optional[str] = None
    claims: Dict[str, Any] = Field(default_factory=dict)


class SupabaseJWTVerifier:
    """
    Cryptographic verification service for Supabase Auth JWT access tokens.
    Fetches and caches public keys from SUPABASE_JWKS_URL (supports ES256 / RS256).
    """

    def __init__(self):
        self._jwks_client: Optional[PyJWKClient] = None
        self._last_jwks_url: Optional[str] = None

    @property
    def jwks_client(self) -> Optional[PyJWKClient]:
        url = settings.resolved_jwks_url
        if not url:
            return None
        if self._jwks_client is None or self._last_jwks_url != url:
            self._jwks_client = PyJWKClient(
                uri=url,
                cache_keys=True,
                max_cached_keys=16,
                lifespan=3600,
            )
            self._last_jwks_url = url
        return self._jwks_client

    def verify_token(self, token: str) -> AuthenticatedUser:
        """
        Validates JWT signature, expiration, subject format, and claims.
        Raises HTTPException(401) on any cryptographic or claim validation failure.
        Never logs the token or exposes sensitive secrets.
        """
        if not token or not isinstance(token, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        client = self.jwks_client
        if client is None:
            logger.error("Supabase JWKS URL is not configured.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service configuration error.",
            )

        try:
            # 1. Retrieve signing key matching token's 'kid' from JWKS
            signing_key = client.get_signing_key_from_jwt(token)

            # 2. Decode and cryptographically verify signature & expiration
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256", "HS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,  # Verified manually below if present
                },
            )

            # 3. Validate 'sub' claim is a valid UUID
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication token missing subject claim.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            try:
                user_id = UUID(str(sub))
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication token subject is not a valid UUID.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 4. Validate audience if present in token
            aud = payload.get("aud")
            if aud and aud not in {"authenticated", "supabase"}:
                logger.warning("JWT audience mismatch: expected 'authenticated', got '%s'", aud)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token audience.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 5. Validate issuer if present in token
            iss = payload.get("iss")
            if iss and settings.SUPABASE_URL:
                expected_iss = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
                if iss.rstrip("/") != expected_iss:
                    logger.warning("JWT issuer mismatch: expected '%s', got '%s'", expected_iss, iss)
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token issuer.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            return AuthenticatedUser(
                id=user_id,
                email=payload.get("email"),
                role=payload.get("role"),
                claims=payload,
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWKClientError as jwk_err:
            logger.warning("JWK retrieval failed: %s", type(jwk_err).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token key identifier.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as token_err:
            logger.warning("JWT validation failed: %s", type(token_err).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error verifying JWT: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed.",
                headers={"WWW-Authenticate": "Bearer"},
            )


jwt_verifier = SupabaseJWTVerifier()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Optional[Session] = Depends(get_db),
) -> AuthenticatedUser:
    """
    FastAPI dependency resolving authenticated user from verified Supabase Auth JWT.
    Enforces Bearer scheme, validates token cryptographically, and synchronizes
    application profile in public.users to satisfy foreign-key references.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Bearer required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    user = jwt_verifier.verify_token(token)

    # Synchronize application profile non-destructively for foreign keys
    if db is not None:
        try:
            from app.models.user import User
            user_record = db.get(User, user.id)
            if not user_record:
                preferred_email = user.email or f"user_{user.id.hex[:12]}@local.test"
                existing_by_email = db.query(User).filter(User.email == preferred_email).first()
                if existing_by_email:
                    preferred_email = f"{user.id.hex[:8]}_{preferred_email}"
                user_record = User(
                    id=user.id,
                    email=preferred_email,
                    password_hash="supabase_auth_managed",
                )
                db.add(user_record)
                db.commit()
        except Exception as sync_err:
            db.rollback()
            logger.warning("User profile sync encountered error: %s", type(sync_err).__name__)

    return user
