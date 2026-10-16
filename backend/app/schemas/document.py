from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    status: Optional[str] = "uploaded"


class DocumentCreate(DocumentBase):
    user_id: UUID
    storage_path: Optional[str] = None


class DocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    storage_path: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    job_id: UUID
    filename: str
    status: str


class DocumentDeleteResponse(BaseModel):
    message: str
    document_id: UUID
