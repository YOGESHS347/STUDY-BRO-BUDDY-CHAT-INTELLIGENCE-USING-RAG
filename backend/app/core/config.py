import json
import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    # Server Configuration
    ENVIRONMENT: str = "development"
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database Configuration (Supabase PostgreSQL Session Pooler)
    DATABASE_URL: Optional[str] = None

    # Vector Database Configuration (Qdrant)
    VECTOR_STORE_BACKEND: str = "local"
    QDRANT_URL: Optional[str] = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # Supabase Configuration (Storage & Auth)
    STORAGE_BACKEND: str = "local"
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_SECRET_KEY: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "documents"

    # Redis & Asynchronous Worker Configuration
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "rag_ingestion_queue"
    REDIS_CONNECT_TIMEOUT: float = 5.0
    REDIS_SOCKET_TIMEOUT: float = 5.0
    REDIS_MAX_CONNECTIONS: int = 20
    WORKER_MAX_RETRIES: int = 3
    WORKER_RETRY_BACKOFF_SECONDS: float = 5.0
    WORKER_POLL_TIMEOUT_SECONDS: int = 2

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH) if ENV_FILE_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except json.JSONDecodeError:
                    pass
            # Split comma-separated values
            return [origin.strip() for origin in v_stripped.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v]
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def sync_database_url(self) -> Optional[str]:
        """
        Returns SQLAlchemy-compatible PostgreSQL connection string using psycopg driver.
        Translates postgresql:// and postgres:// to postgresql+psycopg:// if needed.
        """
        if not self.DATABASE_URL:
            return None
        url = self.DATABASE_URL.strip()
        if not url:
            return None

        # Standardize prefix for psycopg v3 dialect in SQLAlchemy 2.0
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://") and not url.startswith("postgresql+"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def masked_database_url(self) -> Optional[str]:
        """Safe database URL with password masked for logging/diagnostics."""
        if not self.DATABASE_URL:
            return None
        try:
            from urllib.parse import urlsplit, urlunsplit
            parsed = urlsplit(self.DATABASE_URL)
            if parsed.password:
                netloc = f"{parsed.username or ''}:***@{parsed.hostname or ''}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
            return self.DATABASE_URL
        except Exception:
            return "postgresql://***:***@***"

    @property
    def masked_redis_url(self) -> Optional[str]:
        """Safe Redis URL with password masked for logging/diagnostics."""
        if not self.REDIS_URL:
            return None
        try:
            from urllib.parse import urlsplit, urlunsplit
            parsed = urlsplit(self.REDIS_URL)
            if parsed.password:
                netloc = f"{parsed.username or ''}:***@{parsed.hostname or ''}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
            return self.REDIS_URL
        except Exception:
            return "redis://***:***@***"

    @property
    def effective_service_role_key(self) -> Optional[str]:
        """Returns SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY."""
        return self.SUPABASE_SECRET_KEY or self.SUPABASE_SERVICE_ROLE_KEY

    @property
    def resolved_jwks_url(self) -> Optional[str]:
        """Returns explicit SUPABASE_JWKS_URL or standard Supabase JWKS endpoint."""
        if self.SUPABASE_JWKS_URL:
            return self.SUPABASE_JWKS_URL
        if self.SUPABASE_URL:
            return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def is_cloud_storage_configured(self) -> bool:
        """Returns True if Supabase Storage credentials are fully configured."""
        return bool(self.SUPABASE_URL and self.effective_service_role_key)

    @property
    def resolved_storage_backend(self) -> str:
        """
        Returns the active storage backend ('supabase' or 'local').
        If STORAGE_BACKEND is explicitly defined as 'supabase' or 'local', uses that.
        Otherwise defaults to 'supabase' if cloud storage is configured, else 'local'.
        """
        backend = (self.STORAGE_BACKEND or "").strip().lower()
        if backend in {"supabase", "local"}:
            return backend
        if self.is_cloud_storage_configured:
            return "supabase"
        return "local"


settings = Settings()
