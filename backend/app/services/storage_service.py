import logging
import os
import re
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
LOCAL_STORAGE_BASE = BACKEND_DIR / "storage"


class StorageService:
    """
    Decoupled storage service abstraction supporting:
    1. Production Supabase Storage via REST (strict error handling, zero silent fallback)
    2. Local file-system storage for controlled development and testing
    """

    def __init__(self):
        self.local_base_dir = LOCAL_STORAGE_BASE
        self.local_base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def supabase_url(self) -> Optional[str]:
        return settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else None

    @property
    def service_role_key(self) -> Optional[str]:
        return settings.effective_service_role_key

    @property
    def bucket(self) -> str:
        return settings.SUPABASE_STORAGE_BUCKET or "documents"

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitizes client-provided filename to completely eliminate path traversal
        and dangerous file-system control sequences.
        """
        if not filename:
            return "unnamed_document"

        # Extract only the final basename, normalizing separators
        clean_name = os.path.basename(filename).replace("\\", "/").split("/")[-1]

        # Strip null bytes and control characters
        clean_name = re.sub(r"[\x00-\x1f\x7f]", "", clean_name)

        # Eliminate any directory traversal attempt
        clean_name = clean_name.replace("..", "_")

        # Strip leading/trailing dots and whitespace
        clean_name = clean_name.strip(" .")

        return clean_name if clean_name else "document"

    def generate_storage_path(
        self,
        user_id: Union[UUID, str],
        document_id: Union[UUID, str],
        filename: str,
    ) -> str:
        """
        Constructs a deterministic, tenant-isolated logical storage object path:
        {user_id}/{document_id}/{clean_filename}
        """
        clean_filename = self.sanitize_filename(filename)
        return f"{str(user_id)}/{str(document_id)}/{clean_filename}"

    def get_object_path(self, storage_path: str) -> str:
        """
        Normalizes the storage path into a bucket-relative object path.
        If the path starts with '<bucket>/', the prefix is stripped to prevent
        '/documents/documents/...' duplication in the Supabase Storage REST URL.
        """
        if not storage_path:
            return ""
        normalized = storage_path.replace("\\", "/").strip("/")
        bucket_prefix = f"{self.bucket}/"
        if normalized.startswith(bucket_prefix):
            return normalized[len(bucket_prefix):]
        return normalized

    def is_cloud_storage_configured(self) -> bool:
        """Returns True if Supabase Storage credentials are fully configured."""
        return bool(self.supabase_url and self.service_role_key)

    def verify_bucket(self) -> bool:
        """
        Verifies that the configured Supabase Storage bucket exists.
        Never creates a public bucket silently.
        """
        if not self.is_cloud_storage_configured():
            logger.warning("Cannot verify bucket: Supabase Storage is not configured.")
            return False

        url = f"{self.supabase_url}/storage/v1/bucket/{self.bucket}"
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    logger.info("Verified Supabase Storage bucket '%s' exists.", self.bucket)
                    return True
                elif response.status_code == 404:
                    logger.error(
                        "Supabase Storage bucket '%s' not found. "
                        "Please create a private bucket named '%s' in your Supabase dashboard.",
                        self.bucket,
                        self.bucket,
                    )
                    return False
                else:
                    logger.error("Failed to verify bucket '%s' (HTTP %d)", self.bucket, response.status_code)
                    return False
        except Exception as e:
            logger.error("Bucket verification encountered network error: %s", type(e).__name__)
            return False

    def upload_file(
        self,
        storage_path: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Uploads file content to the storage path.
        - In 'supabase' mode: Strictly uploads to Supabase Storage. Raises RuntimeError
          on failure without falling back to local disk.
        - In 'local' mode: Persists to backend/storage/ for local development/testing.
        """
        object_path = self.get_object_path(storage_path)
        backend = settings.resolved_storage_backend

        if backend == "supabase":
            if not self.is_cloud_storage_configured():
                raise RuntimeError(
                    "STORAGE_BACKEND is 'supabase', but SUPABASE_URL or "
                    "SUPABASE_SERVICE_ROLE_KEY is not configured."
                )

            url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_path}"
            headers = {
                "Authorization": f"Bearer {self.service_role_key}",
                "apikey": self.service_role_key,
                "Content-Type": content_type or "application/octet-stream",
                "x-upsert": "true",
            }
            try:
                with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
                    response = client.post(url, headers=headers, content=content)
                    if response.status_code in {200, 201}:
                        logger.info("Uploaded to Supabase Storage: %s (size: %d bytes)", object_path, len(content))
                        return storage_path
                    else:
                        logger.error(
                            "Supabase Storage upload failed with status %d: %s",
                            response.status_code,
                            response.text,
                        )
                        raise RuntimeError(f"Supabase Storage upload rejected with HTTP {response.status_code}")
            except httpx.HTTPError as http_err:
                logger.error("Network error uploading to Supabase Storage: %s", type(http_err).__name__)
                raise RuntimeError(f"Failed to connect to Supabase Storage: {type(http_err).__name__}") from http_err
            except RuntimeError:
                raise
            except Exception as e:
                logger.error("Unexpected error uploading to Supabase Storage: %s", type(e).__name__)
                raise RuntimeError(f"Supabase Storage upload failed: {type(e).__name__}") from e

        else:
            # Local filesystem storage
            local_dest = self.local_base_dir / object_path
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            local_dest.write_bytes(content)
            logger.info("Persisted to local storage: %s (size: %d bytes)", object_path, len(content))
            return storage_path

    def download_file(self, storage_path: str) -> bytes:
        """
        Retrieves file bytes from storage.
        - In 'supabase' mode: Strictly fetches from Supabase Storage via authenticated REST call.
        - In 'local' mode: Reads from backend/storage/.
        """
        object_path = self.get_object_path(storage_path)
        backend = settings.resolved_storage_backend

        if backend == "supabase":
            if not self.is_cloud_storage_configured():
                raise RuntimeError(
                    "STORAGE_BACKEND is 'supabase', but SUPABASE_URL or "
                    "SUPABASE_SERVICE_ROLE_KEY is not configured."
                )

            url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_path}"
            headers = {
                "Authorization": f"Bearer {self.service_role_key}",
                "apikey": self.service_role_key,
            }
            try:
                with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
                    response = client.get(url, headers=headers)
                    if response.status_code == 200:
                        return response.content
                    elif response.status_code == 404:
                        raise FileNotFoundError(f"File not found in Supabase Storage: {object_path}")
                    else:
                        logger.error(
                            "Supabase Storage download failed with status %d: %s",
                            response.status_code,
                            response.text,
                        )
                        raise RuntimeError(f"Supabase Storage download failed with HTTP {response.status_code}")
            except FileNotFoundError:
                raise
            except httpx.HTTPError as http_err:
                logger.error("Network error downloading from Supabase Storage: %s", type(http_err).__name__)
                raise RuntimeError(f"Supabase Storage connection failed: {type(http_err).__name__}") from http_err
            except Exception as e:
                logger.error("Error downloading from Supabase Storage: %s", type(e).__name__)
                raise RuntimeError(f"Supabase Storage download failed: {type(e).__name__}") from e

        else:
            local_target = self.local_base_dir / object_path
            if local_target.exists() and local_target.is_file():
                return local_target.read_bytes()
            raise FileNotFoundError(f"File not found in local storage: {object_path}")

    def delete_file(self, storage_path: str) -> bool:
        """
        Deletes stored file from the active storage backend.
        """
        object_path = self.get_object_path(storage_path)
        backend = settings.resolved_storage_backend
        deleted = False

        if backend == "supabase":
            if not self.is_cloud_storage_configured():
                logger.warning("Cannot delete from Supabase Storage: credentials missing.")
                return False

            url = f"{self.supabase_url}/storage/v1/object/{self.bucket}"
            headers = {
                "Authorization": f"Bearer {self.service_role_key}",
                "apikey": self.service_role_key,
            }
            try:
                with httpx.Client(timeout=15.0) as client:
                    response = client.request(
                        "DELETE",
                        url,
                        headers=headers,
                        json={"prefixes": [object_path]},
                    )
                    if response.status_code in {200, 204}:
                        deleted = True
                        logger.info("Deleted from Supabase Storage: %s", object_path)
                    else:
                        logger.warning(
                            "Supabase Storage delete returned HTTP %d for %s",
                            response.status_code,
                            object_path,
                        )
            except Exception as e:
                logger.warning("Error deleting from Supabase Storage (%s): %s", object_path, type(e).__name__)
            return deleted

        else:
            local_target = self.local_base_dir / object_path
            if local_target.exists() and local_target.is_file():
                try:
                    local_target.unlink()
                    deleted = True
                    logger.info("Deleted from local storage: %s", object_path)
                    # Clean up empty parent directories up to local_base_dir
                    parent = local_target.parent
                    while parent != self.local_base_dir and parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                except Exception as e:
                    logger.warning("Error deleting local file %s: %s", object_path, e)
            return deleted

    def file_exists(self, storage_path: str) -> bool:
        """Checks if a file exists in the active storage backend."""
        object_path = self.get_object_path(storage_path)
        backend = settings.resolved_storage_backend

        if backend == "supabase":
            if not self.is_cloud_storage_configured():
                return False
            url = f"{self.supabase_url}/storage/v1/object/info/{self.bucket}/{object_path}"
            headers = {
                "Authorization": f"Bearer {self.service_role_key}",
                "apikey": self.service_role_key,
            }
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.get(url, headers=headers)
                    return res.status_code == 200
            except Exception:
                return False
        else:
            local_target = self.local_base_dir / object_path
            return local_target.exists() and local_target.is_file()

    def create_signed_url(self, storage_path: str, expires_in: int = 300) -> Optional[str]:
        """
        Generates a short-lived signed URL for downloading private Supabase Storage objects.
        Returns None if cloud storage is not configured or in local storage mode.
        """
        if not self.is_cloud_storage_configured():
            return None
        object_path = self.get_object_path(storage_path)
        url = f"{self.supabase_url}/storage/v1/object/sign/{self.bucket}/{object_path}"
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, headers=headers, json={"expiresIn": expires_in})
                if response.status_code == 200:
                    data = response.json()
                    signed_path = data.get("signedURL")
                    if signed_path:
                        if signed_path.startswith("http"):
                            return signed_path
                        return f"{self.supabase_url}{signed_path}"
        except Exception as e:
            logger.warning("Failed to generate signed URL for %s: %s", object_path, type(e).__name__)
        return None

    def check_health(self) -> str:
        """
        Returns storage health status without leaking secrets:
        - 'connected': cloud bucket exists and is accessible
        - 'disconnected': cloud backend configured but unreachable or bucket missing
        - 'not_configured': cloud backend requested but credentials missing
        - 'local_storage_ready': local filesystem storage active and writable
        """
        backend = settings.resolved_storage_backend
        if backend == "supabase":
            if not self.is_cloud_storage_configured():
                return "not_configured"
            try:
                if self.verify_bucket():
                    return "connected"
                return "disconnected"
            except Exception:
                return "disconnected"
        else:
            try:
                self.local_base_dir.mkdir(parents=True, exist_ok=True)
                test_file = self.local_base_dir / ".health_check"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink()
                return "local_storage_ready"
            except Exception:
                return "disconnected"


storage_service = StorageService()
