import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Union
from uuid import UUID

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

# Centralized path resolution for RAG engine modules
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
RAG_ENGINE_DIR = PROJECT_ROOT / "document-intelligence-rag"

if str(RAG_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_ENGINE_DIR))


class IngestionService:
    """
    Orchestrates the multi-user document ingestion pipeline:
    1. Downloads file from storage abstraction.
    2. Uses existing RAG engine loaders (load_file_with_metadata).
    3. Generates vector embeddings via existing EmbeddingModel.
    4. Upserts tenant-isolated vectors into Qdrant Cloud.
    5. Updates IngestionJob and Document statuses in database.
    """

    @staticmethod
    def process_document_job(
        job_id: Union[UUID, str],
        document_id: Union[UUID, str],
        user_id: Union[UUID, str],
        storage_path: str,
        filename: str,
    ) -> None:
        """
        Executes document ingestion and vectorization in the background.
        Ensures strict cleanup of temporary processing files and robust error handling.
        """
        logger.info(
            "Starting ingestion job: job_id=%s, doc_id=%s, user_id=%s, filename=%s",
            job_id,
            document_id,
            user_id,
            filename,
        )

        db = SessionLocal() if SessionLocal else None
        if db is None:
            logger.error("Ingestion failed: database session could not be established.")
            return

        job_uuid = UUID(str(job_id))
        doc_uuid = UUID(str(document_id))
        user_uuid = UUID(str(user_id))

        temp_file_path = None

        try:
            # 1. Update job and document to "processing"
            job = db.get(IngestionJob, job_uuid)
            doc = db.get(Document, doc_uuid)

            if job and job.status == "completed" and doc and doc.status == "completed":
                logger.info("[IDEMPOTENCY] Ingestion job %s is already completed. Skipping.", job_uuid)
                return

            if job:
                job.status = "processing"
                job.started_at = datetime.now(timezone.utc)
            if doc:
                doc.status = "processing"
            db.commit()

            # 2. Retrieve file content from storage
            file_bytes = storage_service.download_file(storage_path)

            # 3. Create secure temporary file for the existing RAG loaders
            suffix = Path(filename).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = Path(temp_file.name)

            # 4. Load and chunk file using existing RAG engine logic
            from ingestion.ingestion import load_file_with_metadata

            chunks = list(
                load_file_with_metadata(
                    temp_file_path,
                    user_id=str(user_uuid),
                    document_id=str(doc_uuid),
                )
            )

            logger.info("Generated %d chunks for document %s", len(chunks), doc_uuid)

            if not chunks:
                logger.warning("No text content could be extracted from %s", filename)
                if job:
                    job.status = "completed"
                    job.total_chunks = 0
                    job.processed_chunks = 0
                    job.completed_at = datetime.now(timezone.utc)
                if doc:
                    doc.status = "completed"
                db.commit()
                return

            # Ensure metadata consistency across all chunks
            for chunk in chunks:
                chunk.metadata["user_id"] = str(user_uuid)
                chunk.metadata["document_id"] = str(doc_uuid)
                chunk.metadata["source"] = filename

            # 5. Generate embeddings using existing EmbeddingModel
            from embeddings.embeddings import EmbeddingModel

            embed_model = EmbeddingModel()
            embeddings = embed_model.embed_documents(chunks)

            # 6. Upsert vectors to vector store (Qdrant Cloud when configured)
            from vector_store.vector_store import VectorStore

            store = VectorStore()
            try:
                store.add_documents(
                    documents=chunks,
                    embeddings=embeddings,
                    user_id=str(user_uuid),
                    document_id=str(doc_uuid),
                )
            finally:
                store.close()

            # 7. Update records to "completed"
            if job:
                job.total_chunks = len(chunks)
                job.processed_chunks = len(chunks)
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
            if doc:
                doc.status = "completed"
            db.commit()

            logger.info("Ingestion job completed successfully for document %s", doc_uuid)

        except Exception as exc:
            logger.exception("Ingestion job %s encountered fatal error: %s", job_id, exc)
            if db:
                try:
                    job = db.get(IngestionJob, job_uuid)
                    doc = db.get(Document, doc_uuid)
                    safe_error = f"Ingestion error: {type(exc).__name__}"
                    if job:
                        job.status = "failed"
                        job.error_message = safe_error
                        job.completed_at = datetime.now(timezone.utc)
                    if doc:
                        doc.status = "failed"
                    db.commit()
                except Exception as db_exc:
                    logger.error("Failed to record error status in DB: %s", db_exc)
        finally:
            # 8. Clean up temporary processing file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as cleanup_err:
                    logger.warning("Failed to clean up temp file %s: %s", temp_file_path, cleanup_err)

            if db:
                db.close()


ingestion_service = IngestionService()
