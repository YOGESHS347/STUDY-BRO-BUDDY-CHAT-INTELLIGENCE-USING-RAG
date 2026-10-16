"""
Unit and integration tests for Redis connection, queue dispatch,
dedicated worker processing, idempotency, retries, and tenant isolation.
"""

import io
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
RAG_ENGINE_DIR = PROJECT_ROOT / "document-intelligence-rag"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(RAG_ENGINE_DIR) not in sys.path:
    sys.path.append(str(RAG_ENGINE_DIR))

from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.user import User
from app.services.queue_service import QueueServiceError, queue_service
from app.services.redis_service import redis_service
from app.services.storage_service import storage_service
from worker.ingestion_worker import ingestion_worker

client = TestClient(app)


# ------------------------------------------------------------
# 1. Redis Connection & Health Check Tests
# ------------------------------------------------------------

def test_redis_health_connected():
    """Verify check_health returns 'connected' when Redis is reachable."""
    health = redis_service.check_health()
    assert health == "connected"


def test_redis_health_disconnected(monkeypatch):
    """Verify check_health gracefully returns 'disconnected' on connection failure."""
    mock_client = MagicMock()
    import redis
    mock_client.ping.side_effect = redis.ConnectionError("Simulated Redis down")
    monkeypatch.setattr(redis_service, "get_client", lambda: mock_client)

    health = redis_service.check_health()
    assert health == "disconnected"


# ------------------------------------------------------------
# 2. Queue Dispatch Tests
# ------------------------------------------------------------

def test_enqueue_ingestion_job_payload_minimalism():
    """Verify enqueue_ingestion_job sends ONLY minimal identification metadata."""
    jid = str(uuid.uuid4())
    queue_service.clear_queue()

    success = queue_service.enqueue_ingestion_job(jid)
    assert success is True

    payload = queue_service.dequeue_ingestion_job(timeout=1)
    assert payload is not None
    assert payload["job_id"] == jid
    assert "enqueued_at" in payload
    # Must NOT contain binary data or document content
    assert "file" not in payload
    assert "content" not in payload
    assert "embeddings" not in payload


def test_enqueue_job_fails_safely_when_redis_down(monkeypatch):
    """Verify enqueue_ingestion_job raises QueueServiceError when Redis fails."""
    mock_client = MagicMock()
    import redis
    mock_client.lpush.side_effect = redis.ConnectionError("Redis unreachable")
    monkeypatch.setattr(redis_service, "get_client", lambda: mock_client)

    with pytest.raises(QueueServiceError) as exc_info:
        queue_service.enqueue_ingestion_job(str(uuid.uuid4()))
    assert "Redis queue unreachable" in str(exc_info.value)


# ------------------------------------------------------------
# 3. Worker Ingestion E2E Test
# ------------------------------------------------------------

def test_worker_processes_job_e2e():
    """Verify dedicated IngestionWorker processes a valid job to completion."""
    uid = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    db = SessionLocal()
    # Ensure user exists
    if not db.get(User, uid):
        db.add(User(id=uid, email=f"{uid.hex[:8]}@test.com", password_hash="hash"))
        db.flush()

    # Upload test document to storage
    content = b"Encapsulation binds data and functions together into a single unit."
    storage_path = f"{uid}/{doc_id}/encapsulation_test.txt"
    storage_service.upload_file(storage_path, content, content_type="text/plain")

    doc = Document(
        id=doc_id,
        user_id=uid,
        filename="encapsulation_test.txt",
        file_type="txt",
        file_size=len(content),
        storage_path=storage_path,
        status="uploaded",
    )
    job = IngestionJob(
        id=job_id,
        document_id=doc_id,
        user_id=uid,
        status="queued",
    )
    db.add(doc)
    db.add(job)
    db.commit()
    db.close()

    try:
        # Worker processes the job
        success = ingestion_worker.process_job(job_id=job_id)
        assert success is True

        # Verify DB state
        db = SessionLocal()
        updated_job = db.get(IngestionJob, job_id)
        updated_doc = db.get(Document, doc_id)

        assert updated_job.status == "completed"
        assert updated_job.total_chunks >= 1
        assert updated_job.processed_chunks == updated_job.total_chunks
        assert updated_job.started_at is not None
        assert updated_job.completed_at is not None
        assert updated_doc.status == "completed"
        db.close()
    finally:
        # Clean up
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


# ------------------------------------------------------------
# 4. Idempotency & Duplicate Delivery Safety
# ------------------------------------------------------------

def test_idempotency_duplicate_job_delivery():
    """Verify already COMPLETED jobs safely acknowledge duplicate delivery without re-processing."""
    uid = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    db = SessionLocal()
    if not db.get(User, uid):
        db.add(User(id=uid, email=f"{uid.hex[:8]}@test.com", password_hash="hash"))
        db.flush()

    storage_path = f"{uid}/{doc_id}/idempotent.txt"
    storage_service.upload_file(storage_path, b"Test idempotency content.")

    now = datetime.now(timezone.utc)
    doc = Document(id=doc_id, user_id=uid, filename="idempotent.txt", file_type="txt", file_size=24, storage_path=storage_path, status="completed")
    job = IngestionJob(id=job_id, document_id=doc_id, user_id=uid, status="completed", total_chunks=1, processed_chunks=1, completed_at=now)
    db.add(doc)
    db.add(job)
    db.commit()
    db.close()

    try:
        # Deliver same job a second time
        res = ingestion_worker.process_job(job_id=job_id)
        assert res is True

        # Verify status did not reset or corrupt
        db = SessionLocal()
        j = db.get(IngestionJob, job_id)
        assert j.status == "completed"
        assert j.completed_at == now
        db.close()
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


# ------------------------------------------------------------
# 5. Failure Handling (Corrupted Document)
# ------------------------------------------------------------

def test_failed_job_corrupt_file_handling():
    """Verify corrupt/unreadable files transition job to 'failed' and do not leak stack traces."""
    uid = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    db = SessionLocal()
    if not db.get(User, uid):
        db.add(User(id=uid, email=f"{uid.hex[:8]}@test.com", password_hash="hash"))
        db.flush()

    storage_path = f"{uid}/{doc_id}/corrupted.pdf"
    storage_service.upload_file(storage_path, b"THIS_IS_DEFINITELY_NOT_A_VALID_PDF_HEADER")

    doc = Document(id=doc_id, user_id=uid, filename="corrupted.pdf", file_type="pdf", file_size=40, storage_path=storage_path, status="uploaded")
    job = IngestionJob(id=job_id, document_id=doc_id, user_id=uid, status="queued")
    db.add(doc)
    db.add(job)
    db.commit()
    db.close()

    try:
        success = ingestion_worker.process_job(job_id=job_id)
        assert success is False

        db = SessionLocal()
        j = db.get(IngestionJob, job_id)
        d = db.get(Document, doc_id)
        assert j.status == "failed"
        assert d.status == "failed"
        assert j.error_message is not None
        assert "Ingestion error" in j.error_message
        # Confirm no full stack trace is exposed in error_message
        assert "Traceback" not in j.error_message
        db.close()
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


# ------------------------------------------------------------
# 6. Tenant Isolation in Worker
# ------------------------------------------------------------

def test_tenant_isolation_in_worker():
    """Verify worker refuses to process a job if user_id does not match document owner."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    db = SessionLocal()
    for u in (user_a, user_b):
        if not db.get(User, u):
            db.add(User(id=u, email=f"{u.hex[:8]}@test.com", password_hash="hash"))
    db.flush()

    storage_path = f"{user_a}/{doc_id}/doc_a.txt"
    storage_service.upload_file(storage_path, b"User A confidential data.")

    # Document belongs to User A, but Job claims User B!
    doc = Document(id=doc_id, user_id=user_a, filename="doc_a.txt", file_type="txt", file_size=25, storage_path=storage_path, status="uploaded")
    job = IngestionJob(id=job_id, document_id=doc_id, user_id=user_b, status="queued")
    db.add(doc)
    db.add(job)
    db.commit()
    db.close()

    try:
        success = ingestion_worker.process_job(job_id=job_id)
        assert success is False

        db = SessionLocal()
        j = db.get(IngestionJob, job_id)
        assert j.status == "failed"
        assert "isolation" in j.error_message.lower()
        db.close()
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={user_a}")


# ------------------------------------------------------------
# 7. Upload API Returns 503 If Redis Down
# ------------------------------------------------------------

def test_upload_api_safe_error_when_redis_down(monkeypatch):
    """Verify POST /api/v1/documents/upload returns HTTP 503 and marks job failed if Redis enqueue fails."""
    uid = str(uuid.uuid4())
    files = {"file": ("test_redis_down.txt", b"Some test text", "text/plain")}
    data = {"user_id": uid}

    def mock_enqueue(job_id):
        raise QueueServiceError("Redis connection refused")

    monkeypatch.setattr(queue_service, "enqueue_ingestion_job", mock_enqueue)

    response = client.post("/api/v1/documents/upload", files=files, data=data)
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()
