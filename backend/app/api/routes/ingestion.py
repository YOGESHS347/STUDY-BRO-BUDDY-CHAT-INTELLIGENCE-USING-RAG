import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.schemas.ingestion_job import IngestionJobStatusResponse
from app.services.document_service import document_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{job_id}", response_model=IngestionJobStatusResponse)
def get_ingestion_job_status(
    job_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_id: Optional[UUID] = Query(None, description="Optional legacy user_id - ignored in favor of authenticated token"),
    db: Optional[Session] = Depends(get_db),
) -> IngestionJobStatusResponse:
    """
    Retrieves the status, chunking progress, and timestamps for an ingestion job.
    Enforces strict tenant isolation: Caller can only inspect their own ingestion jobs.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    job = document_service.get_ingestion_job(db, job_id=job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found or does not belong to the specified user.",
        )

    return IngestionJobStatusResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status,
        total_chunks=job.total_chunks or 0,
        processed_chunks=job.processed_chunks or 0,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
