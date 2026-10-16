import logging
import mimetypes
import uuid
from pathlib import Path
from typing import List, Optional, Union
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.document_service import document_service
from app.services.ingestion_service import ingestion_service
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".txt"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(..., description="Uploaded document file"),
    user_id: Optional[UUID] = Form(None, description="Optional legacy user_id - ignored in favor of authenticated token"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Uploads a document under the authenticated user's identity.
    Client-provided user_id is rejected if it conflicts with authenticated JWT identity.
    Persists file via storage service, creates tracking records, and schedules background ingestion.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    # Validate that client did not attempt identity spoofing
    if user_id is not None and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client-provided user_id conflicts with authenticated token identity.",
        )

    auth_user_id = current_user.id

    # 1. Validate filename and extension
    original_filename = file.filename or ""
    suffix = Path(original_filename).suffix.lower()

    if not suffix or suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # 2. Read and validate file content
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty files are not allowed for ingestion.",
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size} bytes) exceeds the maximum allowed 50 MB limit.",
        )

    # 3. Sanitize filename against directory traversal
    clean_filename = storage_service.sanitize_filename(original_filename)

    # 4. Generate UUIDs and tenant-isolated storage path
    document_id = uuid.uuid4()
    job_id = uuid.uuid4()
    storage_path = storage_service.generate_storage_path(
        user_id=auth_user_id,
        document_id=document_id,
        filename=clean_filename,
    )

    logger.info(
        "Initiating document upload: doc_id=%s, user_id=%s, filename=%s, size=%d",
        document_id,
        auth_user_id,
        clean_filename,
        file_size,
    )

    # 5. Persist file content via storage service (cloud or local)
    try:
        storage_service.upload_file(
            storage_path=storage_path,
            content=content,
            content_type=file.content_type,
        )
    except Exception as upload_err:
        logger.exception("Storage service upload failed: %s", type(upload_err).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist uploaded document in storage.",
        )

    # 6. Create Document and IngestionJob records
    try:
        from app.models.user import User

        # Ensure user record exists for database foreign keys
        user_record = db.get(User, auth_user_id)
        if not user_record:
            user_record = User(
                id=auth_user_id,
                email=current_user.email or f"user_{auth_user_id.hex[:12]}@local.test",
                password_hash="supabase_auth_managed",
            )
            db.add(user_record)
            db.flush()

        doc = Document(
            id=document_id,
            user_id=auth_user_id,
            filename=clean_filename,
            file_type=suffix.lstrip("."),
            file_size=file_size,
            storage_path=storage_path,
            status="uploaded",
        )
        job = IngestionJob(
            id=job_id,
            document_id=document_id,
            user_id=auth_user_id,
            status="queued",
        )
        db.add(doc)
        db.add(job)
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.exception("Database transaction failed during upload: %s", type(db_err).__name__)
        storage_service.delete_file(storage_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record document metadata in database.",
        )

    # 7. Dispatch asynchronous background ingestion to Redis queue
    from app.services.queue_service import QueueServiceError, queue_service

    try:
        queue_service.enqueue_ingestion_job(job.id)
    except QueueServiceError as queue_err:
        logger.error("Failed to enqueue ingestion job %s: %s", job.id, queue_err)
        try:
            job.status = "failed"
            job.error_message = "Ingestion queue temporarily unavailable"
            doc.status = "failed"
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document ingestion service is temporarily unavailable. Please try again later.",
        )

    return DocumentUploadResponse(
        document_id=doc.id,
        job_id=job.id,
        filename=doc.filename,
        status="queued",
    )


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_id: Optional[UUID] = Query(None, description="Optional legacy user_id (ignored in favor of authenticated token)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Optional[Session] = Depends(get_db),
) -> List[DocumentResponse]:
    """Retrieve all documents belonging to the authenticated user."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )
    return document_service.get_documents_by_user(db, user_id=current_user.id, skip=skip, limit=limit)


@router.get("/{document_id}/download")
def download_document(
    document_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_id: Optional[UUID] = Query(None, description="Optional legacy user_id (ignored in favor of authenticated token)"),
    db: Optional[Session] = Depends(get_db),
):
    """
    Secure document download endpoint:
    1. Verifies that the document exists and belongs to the authenticated user.
    2. Downloads raw bytes from storage abstraction.
    3. Streams content safely with Content-Disposition and appropriate media type.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    doc = document_service.get_document_by_id(db, document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or does not belong to the specified user.",
        )

    if not doc.storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document has no associated storage location.",
        )

    try:
        content = storage_service.download_file(doc.storage_path)
    except FileNotFoundError:
        logger.error("Document file not found in storage: doc_id=%s, path=%s", document_id, doc.storage_path)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found in storage.",
        )
    except Exception as exc:
        logger.exception("Failed to retrieve document from storage: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document from storage.",
        )

    media_type, _ = mimetypes.guess_type(doc.filename)
    if not media_type:
        media_type = "application/octet-stream"

    clean_filename = storage_service.sanitize_filename(doc.filename)

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{clean_filename}"',
            "Content-Length": str(len(content)),
        },
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_id: Optional[UUID] = Query(None, description="Optional legacy user_id (ignored)"),
    db: Optional[Session] = Depends(get_db),
) -> DocumentResponse:
    """Retrieve metadata for a specific document belonging to the authenticated user."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    doc = document_service.get_document_by_id(db, document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or does not belong to the specified user.",
        )
    return doc


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_id: Optional[UUID] = Query(None, description="Optional legacy user_id (ignored)"),
    db: Optional[Session] = Depends(get_db),
) -> DocumentDeleteResponse:
    """
    Deletes a document, enforcing strict multi-tenant ownership:
    1. Verifies ownership against authenticated user.
    2. Removes vector embeddings from Qdrant Cloud for this document_id and user_id.
    3. Removes stored file from storage abstraction.
    4. Deletes document record and cascading ingestion jobs from database.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    doc = document_service.get_document_by_id(db, document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or does not belong to the specified user.",
        )

    storage_path = doc.storage_path

    # 1. Clean up vector embeddings in VectorStore
    try:
        from vector_store.vector_store import VectorStore

        store = VectorStore()
        try:
            store.delete_document_vectors(document_id=str(document_id), user_id=str(current_user.id))
        finally:
            store.close()
    except Exception as vec_err:
        logger.warning("Failed to delete vectors for doc %s: %s", document_id, type(vec_err).__name__)

    # 2. Clean up stored file
    if storage_path:
        try:
            storage_service.delete_file(storage_path)
        except Exception as store_err:
            logger.warning("Failed to delete file %s from storage: %s", storage_path, type(store_err).__name__)

    # 3. Delete from DB
    deleted = document_service.delete_document(db, document_id=document_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to delete document from database.",
        )

    logger.info("Successfully deleted document %s for user %s", document_id, current_user.id)

    return DocumentDeleteResponse(
        message="Document and associated vectors deleted successfully.",
        document_id=document_id,
    )
