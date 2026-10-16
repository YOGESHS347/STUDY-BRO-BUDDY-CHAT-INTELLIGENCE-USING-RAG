import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.ingestion_job import IngestionJob


class DocumentService:
    """
    Service abstraction for document metadata, user ownership, and ingestion jobs.
    In future phases, this service connects to Supabase Storage and triggers document chunking.
    """

    @staticmethod
    def get_documents_by_user(
        db: Session,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """Retrieve all documents belonging to a specific user (multi-user tenant isolation)."""
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_document_by_id(
        db: Session,
        document_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[Document]:
        """Retrieve a specific document, optionally enforcing user ownership."""
        stmt = select(Document).where(Document.id == document_id)
        if user_id is not None:
            stmt = stmt.where(Document.user_id == user_id)
        return db.scalars(stmt).first()

    @staticmethod
    def create_document_metadata(
        db: Session,
        user_id: uuid.UUID,
        filename: str,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
        storage_path: Optional[str] = None,
        status: str = "uploaded",
    ) -> Document:
        """Create a new document metadata entry."""
        doc = Document(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            status=status,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def update_document_status(
        db: Session,
        document_id: uuid.UUID,
        status: str,
    ) -> Optional[Document]:
        """Update processing status of a document."""
        doc = db.get(Document, document_id)
        if doc:
            doc.status = status
            db.commit()
            db.refresh(doc)
        return doc

    @staticmethod
    def create_ingestion_job(
        db: Session,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> IngestionJob:
        """Create an ingestion tracking job for background chunking and vector indexing."""
        job = IngestionJob(
            document_id=document_id,
            user_id=user_id,
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_ingestion_job(
        db: Session,
        job_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[IngestionJob]:
        """Retrieve an ingestion job, enforcing user ownership if user_id is provided."""
        stmt = select(IngestionJob).where(IngestionJob.id == job_id)
        if user_id is not None:
            stmt = stmt.where(IngestionJob.user_id == user_id)
        return db.scalars(stmt).first()

    @staticmethod
    def delete_document(
        db: Session,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Delete a document and its cascading records, enforcing strict user ownership.
        Returns True if deleted, False if document was not found or does not belong to user.
        """
        doc = DocumentService.get_document_by_id(db, document_id=document_id, user_id=user_id)
        if not doc:
            return False

        db.delete(doc)
        db.commit()
        return True


document_service = DocumentService()
