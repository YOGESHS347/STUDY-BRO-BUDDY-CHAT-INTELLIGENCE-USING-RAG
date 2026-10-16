from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class IngestionJobBase(BaseModel):
    document_id: UUID
    user_id: UUID
    status: str = "queued"
    total_chunks: Optional[int] = 0
    processed_chunks: Optional[int] = 0
    error_message: Optional[str] = None


class IngestionJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    status: str
    total_chunks: Optional[int] = 0
    processed_chunks: Optional[int] = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IngestionJobStatusResponse(BaseModel):
    job_id: UUID
    document_id: UUID
    status: str
    total_chunks: Optional[int] = 0
    processed_chunks: Optional[int] = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
