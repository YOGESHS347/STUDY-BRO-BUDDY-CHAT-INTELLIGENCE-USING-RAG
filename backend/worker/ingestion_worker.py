"""
Core worker logic for processing an ingestion job.
Ensures strict tenant isolation, idempotency, progress tracking,
retry policy for transient errors, and robust cleanup.
Reuses existing RAG engine loaders, embeddings, and vector store.
"""

import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

# Ensure paths for backend and document-intelligence-rag
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
RAG_ENGINE_DIR = PROJECT_ROOT / "document-intelligence-rag"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(RAG_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_ENGINE_DIR))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.services.redis_service import redis_service
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

# Transient error types eligible for retry
TRANSIENT_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    OSError,
)


class IngestionWorker:
    """
    Dedicated worker processor executing asynchronous document ingestion.
    """

    @staticmethod
    def is_transient_error(exc: Exception) -> bool:
        """
        Determines if an exception is a transient network/connection glitch
        eligible for retry, or a permanent failure (e.g. corrupt file, invalid schema).
        """
        if isinstance(exc, TRANSIENT_EXCEPTIONS):
            return True
        exc_str = str(exc).lower()
        if any(msg in exc_str for msg in ("timeout", "connection refused", "network", "retry")):
            return True
        return False

    @classmethod
    def process_job(
        cls,
        job_id: Union[UUID, str],
        retry_count: int = 0,
    ) -> bool:
        """
        Processes a single ingestion job retrieved from Redis:
        1. Queries authoritative PostgreSQL state.
        2. Verifies document and user ownership.
        3. Enforces idempotency via DB status and distributed lock.
        4. Downloads file from storage abstraction.
        5. Calls existing RAG engine loaders.
        6. Updates real chunk counters in PostgreSQL.
        7. Generates embeddings and upserts to Qdrant.
        8. Marks job and document completed.
        9. Applies safe retry policy for transient errors.
        """
        job_uuid = UUID(str(job_id))
        lock_key = f"ingestion_lock:{job_uuid}"
        lock_acquired = False
        redis_client = None

        # 1. Distributed lock acquisition (prevent concurrent duplicate worker execution)
        try:
            redis_client = redis_service.get_client()
            lock_acquired = bool(redis_client.set(lock_key, "active", nx=True, ex=600))
            if not lock_acquired:
                logger.warning(
                    "[WORKER] Job %s is currently locked by another active worker. Skipping.",
                    job_uuid,
                )
                return False
        except Exception as lock_err:
            logger.warning("[WORKER] Redis lock check non-fatal warning: %s", lock_err)

        db = SessionLocal() if SessionLocal else None
        if db is None:
            logger.error("[WORKER] Database session unavailable for job %s", job_uuid)
            if lock_acquired and redis_client:
                try:
                    redis_client.delete(lock_key)
                except Exception:
                    pass
            return False

        temp_file_path = None
        start_time = time.perf_counter()

        try:
            # 2. Authoritative database lookup
            job = db.get(IngestionJob, job_uuid)
            if not job:
                logger.error("[WORKER] Job %s not found in PostgreSQL database.", job_uuid)
                return False

            doc = db.get(Document, job.document_id)
            if not doc:
                logger.error("[WORKER] Document %s for job %s not found in DB.", job.document_id, job_uuid)
                job.status = "failed"
                job.error_message = "Associated document record missing."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return False

            # 3. Tenant isolation verification: enforce job.user_id == doc.user_id
            if job.user_id != doc.user_id:
                logger.error(
                    "[SECURITY] Tenant isolation violation: job.user_id (%s) != doc.user_id (%s)",
                    job.user_id,
                    doc.user_id,
                )
                job.status = "failed"
                job.error_message = "Tenant isolation mismatch."
                job.completed_at = datetime.now(timezone.utc)
                doc.status = "failed"
                db.commit()
                return False

            user_id = job.user_id
            doc_id = doc.id
            storage_path = doc.storage_path
            filename = doc.filename

            # 4. Idempotency check: if already completed, acknowledge safely
            if job.status == "completed" and doc.status == "completed":
                logger.info("[IDEMPOTENCY] Job %s is already completed. Safely ignoring duplicate.", job_uuid)
                return True

            logger.info(
                "[WORKER] Starting job %s: doc_id=%s, user_id=%s, file=%s, retry=%d",
                job_uuid,
                doc_id,
                user_id,
                filename,
                retry_count,
            )

            # 5. Transition to 'processing'
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            doc.status = "processing"
            db.commit()

            # 6. Retrieve file content from storage abstraction
            if not storage_path:
                raise ValueError("Document storage_path is missing.")

            file_bytes = storage_service.download_file(storage_path)

            # 7. Write to secure temporary file
            suffix = Path(filename).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = Path(temp_file.name)

            # 8. Load & chunk using existing RAG engine loaders
            from ingestion.ingestion import load_file_with_metadata

            chunks = list(
                load_file_with_metadata(
                    temp_file_path,
                    user_id=str(user_id),
                    document_id=str(doc_id),
                )
            )

            total_chunks = len(chunks)
            logger.info("[WORKER] Extracted %d chunks for doc %s", total_chunks, doc_id)

            if total_chunks == 0:
                logger.warning("[WORKER] No extractable text from %s", filename)
                job.total_chunks = 0
                job.processed_chunks = 0
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                doc.status = "completed"
                db.commit()
                return True

            # Record real total chunks
            job.total_chunks = total_chunks
            db.commit()

            # Ensure metadata consistency across all chunks
            for idx, chunk in enumerate(chunks):
                chunk.metadata["user_id"] = str(user_id)
                chunk.metadata["document_id"] = str(doc_id)
                chunk.metadata["source"] = filename
                chunk.metadata["chunk_index"] = idx

            # 9. Generate embeddings using existing EmbeddingModel
            from embeddings.embeddings import EmbeddingModel

            embed_model = EmbeddingModel()
            embeddings = embed_model.embed_documents(chunks)

            # 10. Upsert vectors into VectorStore
            from vector_store.vector_store import VectorStore

            store = VectorStore()
            try:
                store.add_documents(
                    documents=chunks,
                    embeddings=embeddings,
                    user_id=str(user_id),
                    document_id=str(doc_id),
                )
            finally:
                store.close()

            # 11. Update PostgreSQL to completion
            job.processed_chunks = total_chunks
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            doc.status = "completed"
            db.commit()

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                "[WORKER] Successfully completed job %s for doc %s (%d chunks, %.1fms)",
                job_uuid,
                doc_id,
                total_chunks,
                duration_ms,
            )
            return True

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception("[WORKER] Job %s failed after %.1fms: %s", job_uuid, duration_ms, exc)

            is_transient = cls.is_transient_error(exc)
            max_retries = settings.WORKER_MAX_RETRIES or 3

            if is_transient and retry_count < max_retries:
                backoff = settings.WORKER_RETRY_BACKOFF_SECONDS * (2 ** retry_count)
                logger.warning(
                    "[RETRY] Transient failure on job %s (%s). Re-enqueueing (attempt %d/%d) in %.1fs...",
                    job_uuid,
                    type(exc).__name__,
                    retry_count + 1,
                    max_retries,
                    backoff,
                )
                # Rollback current transaction and schedule retry
                if db:
                    db.rollback()
                time.sleep(backoff)
                from app.services.queue_service import queue_service

                try:
                    queue_service.enqueue_ingestion_job(job_uuid)
                except Exception as req_err:
                    logger.error("[RETRY] Failed to re-enqueue job %s: %s", job_uuid, req_err)
                return False

            # Permanent failure or max retries exhausted
            safe_error = f"Ingestion error: {type(exc).__name__}"
            if db:
                try:
                    db.rollback()
                    failed_job = db.get(IngestionJob, job_uuid)
                    if failed_job:
                        failed_job.status = "failed"
                        failed_job.error_message = safe_error
                        failed_job.completed_at = datetime.now(timezone.utc)
                        failed_doc = db.get(Document, failed_job.document_id)
                        if failed_doc:
                            failed_doc.status = "failed"
                        db.commit()
                        logger.info("[WORKER] Marked job %s as failed in database.", job_uuid)
                except Exception as db_fail_err:
                    logger.error("[WORKER] Failed to record failure state in DB: %s", db_fail_err)
            return False

        finally:
            # 12. Cleanup temporary processing file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as cleanup_err:
                    logger.warning("[WORKER] Failed to remove temp file %s: %s", temp_file_path, cleanup_err)

            # 13. Release distributed lock
            if lock_acquired and redis_client:
                try:
                    redis_client.delete(lock_key)
                except Exception:
                    pass

            if db:
                db.close()


ingestion_worker = IngestionWorker()
