import io
import time
import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.user import User
from app.services.storage_service import storage_service

client = TestClient(app)


# ============================================================
# A. Configuration & Security Tests
# ============================================================

def test_supabase_configuration_defaults():
    """Verify Supabase configuration properties and defaults."""
    assert settings.SUPABASE_STORAGE_BUCKET == "documents"
    assert hasattr(settings, "is_cloud_storage_configured")
    assert hasattr(settings, "resolved_storage_backend")


def test_service_role_key_not_exposed_in_openapi_or_health():
    """Verify service role key is never leaked in openapi schema or health check."""
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    health_str = str(res_health.json()).lower()
    assert "service_role" not in health_str
    assert "apikey" not in health_str

    res_docs = client.get("/openapi.json")
    assert res_docs.status_code == 200
    docs_str = str(res_docs.json()).lower()
    assert "service_role" not in docs_str


def test_production_supabase_mode_rejects_without_silent_fallback():
    """
    Verify that in 'supabase' mode, storage upload failure raises RuntimeError
    and does NOT silently fall back to local disk storage.
    """
    uid = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    filename = "test_nofallback.txt"
    storage_path = storage_service.generate_storage_path(uid, doc_id, filename)
    content = b"Production cloud storage payload"

    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-key"):

        # Mock httpx.Client post returning HTTP 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error in Supabase Storage"

        with patch("httpx.Client.post", return_value=mock_response):
            with pytest.raises(RuntimeError) as exc_info:
                storage_service.upload_file(storage_path, content)
            assert "rejected with HTTP 500" in str(exc_info.value)

            # Assert no silent fallback file was written locally
            local_target = storage_service.local_base_dir / storage_service.get_object_path(storage_path)
            assert not local_target.exists()


def test_production_supabase_mode_download_no_silent_fallback():
    """
    Verify that in 'supabase' mode, download failure raises explicit FileNotFoundError
    or RuntimeError and does not read from local disk.
    """
    storage_path = f"mock_user/mock_doc/missing.txt"

    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-service-key"):

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("httpx.Client.get", return_value=mock_response):
            with pytest.raises(FileNotFoundError):
                storage_service.download_file(storage_path)


# ============================================================
# B. Path Sanitization & Deduping
# ============================================================

def test_path_deduping_and_normalization():
    """
    Verify that paths with redundant bucket prefixes ('documents/...')
    are normalized to avoid 'documents/documents/...' REST URLs.
    """
    uid = str(uuid.uuid4())
    did = str(uuid.uuid4())

    # Generated path should be tenant-scoped without bucket prefix
    gen_path = storage_service.generate_storage_path(uid, did, "sample.txt")
    assert gen_path == f"{uid}/{did}/sample.txt"
    assert storage_service.get_object_path(gen_path) == f"{uid}/{did}/sample.txt"

    # Legacy path with 'documents/' prefix should be cleanly stripped
    legacy_path = f"documents/{uid}/{did}/sample.txt"
    assert storage_service.get_object_path(legacy_path) == f"{uid}/{did}/sample.txt"


def test_path_traversal_sanitization():
    """Verify path traversal filenames are neutralized."""
    assert storage_service.sanitize_filename("../../etc/passwd") == "passwd"
    assert storage_service.sanitize_filename("..\\..\\windows\\system32.dll") == "system32.dll"
    assert storage_service.sanitize_filename("safe_report.pdf") == "safe_report.pdf"


# ============================================================
# C. Supabase Storage Mocked REST Operations
# ============================================================

def test_mocked_supabase_upload_and_download_success():
    """Verify upload and download interact correctly with Supabase Storage REST endpoints."""
    uid = str(uuid.uuid4())
    did = str(uuid.uuid4())
    storage_path = storage_service.generate_storage_path(uid, did, "doc.txt")
    file_bytes = b"Hello from Supabase Storage test!"

    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "secret-service-key"):

        mock_upload_resp = MagicMock()
        mock_upload_resp.status_code = 200

        mock_download_resp = MagicMock()
        mock_download_resp.status_code = 200
        mock_download_resp.content = file_bytes

        with patch("httpx.Client.post", return_value=mock_upload_resp) as mock_post, \
             patch("httpx.Client.get", return_value=mock_download_resp) as mock_get:

            # Upload
            result_path = storage_service.upload_file(storage_path, file_bytes, "text/plain")
            assert result_path == storage_path
            assert mock_post.called
            post_args, post_kwargs = mock_post.call_args
            assert "https://mock.supabase.co/storage/v1/object/documents/" in post_args[0]
            assert "documents/documents/" not in post_args[0]
            assert post_kwargs["headers"]["Authorization"] == "Bearer secret-service-key"
            assert post_kwargs["headers"]["apikey"] == "secret-service-key"

            # Download
            downloaded = storage_service.download_file(storage_path)
            assert downloaded == file_bytes
            assert mock_get.called


def test_mocked_supabase_delete():
    """Verify Supabase Storage object delete sends proper prefix and auth."""
    storage_path = "user_1/doc_1/sample.txt"

    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "secret-service-key"):

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.Client.request", return_value=mock_resp) as mock_req:
            res = storage_service.delete_file(storage_path)
            assert res is True
            assert mock_req.called
            method, url = mock_req.call_args[0]
            assert method == "DELETE"
            assert url == "https://mock.supabase.co/storage/v1/object/documents"
            assert mock_req.call_args[1]["json"] == {"prefixes": ["user_1/doc_1/sample.txt"]}


def test_verify_bucket_does_not_create_public_bucket():
    """Verify bucket verification queries bucket existence and reports False if 404."""
    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "secret-service-key"):

        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404

        with patch("httpx.Client.get", return_value=mock_resp_404):
            assert storage_service.verify_bucket() is False

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200

        with patch("httpx.Client.get", return_value=mock_resp_200):
            assert storage_service.verify_bucket() is True


def test_storage_health_states():
    """Verify storage health check reports appropriate states."""
    # 1. Local storage ready
    with patch.object(settings, "STORAGE_BACKEND", "local"):
        assert storage_service.check_health() == "local_storage_ready"

    # 2. Cloud configured and connected
    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-key"), \
         patch.object(storage_service, "verify_bucket", return_value=True):
        assert storage_service.check_health() == "connected"

    # 3. Cloud configured but disconnected
    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", "https://mock.supabase.co"), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-key"), \
         patch.object(storage_service, "verify_bucket", return_value=False):
        assert storage_service.check_health() == "disconnected"

    # 4. Cloud backend chosen but credentials missing
    with patch.object(settings, "STORAGE_BACKEND", "supabase"), \
         patch.object(settings, "SUPABASE_URL", None), \
         patch.object(settings, "SUPABASE_SERVICE_ROLE_KEY", None):
        assert storage_service.check_health() == "not_configured"


# ============================================================
# D. Document Download Endpoint & Tenant Isolation
# ============================================================

def test_document_download_endpoint_success_and_isolation():
    """
    Verify GET /api/v1/documents/{document_id}/download?user_id=<uuid>:
    1. Returns 200 and file content for owner.
    2. Returns 404 for cross-user attempt.
    """
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    file_bytes = b"Tenant-isolated download file content."

    files = {"file": ("isolated_notes.txt", file_bytes, "text/plain")}
    with patch("app.api.routes.documents.ingestion_service.process_document_job"):
        upload_res = client.post("/api/v1/documents/upload", files=files, data={"user_id": user_a})
        assert upload_res.status_code == 202
        doc_id = upload_res.json()["document_id"]

        try:
            # Owner download -> 200 OK
            dl_res = client.get(f"/api/v1/documents/{doc_id}/download?user_id={user_a}")
            assert dl_res.status_code == 200
            assert dl_res.content == file_bytes
            assert 'attachment; filename="isolated_notes.txt"' in dl_res.headers.get("content-disposition", "")

            # Cross-user download -> 404 Not Found
            cross_res = client.get(f"/api/v1/documents/{doc_id}/download?user_id={user_b}")
            assert cross_res.status_code == 404
            assert "not found or does not belong" in cross_res.json()["detail"]

            # Missing document -> 404
            random_id = str(uuid.uuid4())
            missing_res = client.get(f"/api/v1/documents/{random_id}/download?user_id={user_a}")
            assert missing_res.status_code == 404
        finally:
            client.delete(f"/api/v1/documents/{doc_id}?user_id={user_a}")


# ============================================================
# E. Transaction Safety: Upload Failure & Cleanup
# ============================================================

def test_upload_failure_does_not_leave_db_record():
    """Verify failed storage upload does not leave an orphaned document record in DB."""
    uid = str(uuid.uuid4())

    with patch.object(storage_service, "upload_file", side_effect=RuntimeError("Supabase Storage unavailable")):
        files = {"file": ("error_test.txt", b"content", "text/plain")}
        res = client.post("/api/v1/documents/upload", files=files, data={"user_id": uid})
        assert res.status_code == 500

    # Ensure no document record exists for this user
    db = SessionLocal()
    docs = db.query(Document).filter(Document.user_id == uuid.UUID(uid)).all()
    db.close()
    assert len(docs) == 0


def test_db_failure_cleans_up_uploaded_storage_object():
    """Verify that if DB creation fails after storage upload, storage cleanup is triggered."""
    uid = str(uuid.uuid4())

    with patch.object(storage_service, "delete_file") as mock_delete:
        with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("DB Commit Failure")):
            files = {"file": ("db_fail_test.txt", b"cleanup test content", "text/plain")}
            res = client.post("/api/v1/documents/upload", files=files, data={"user_id": uid})
            assert res.status_code == 500
            assert mock_delete.called
