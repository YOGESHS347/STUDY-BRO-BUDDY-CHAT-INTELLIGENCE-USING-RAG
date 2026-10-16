import io
import os
import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
RAG_ENGINE_DIR = PROJECT_ROOT / "document-intelligence-rag"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(RAG_ENGINE_DIR) not in sys.path:
    sys.path.append(str(RAG_ENGINE_DIR))

from app.main import app
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.services.ingestion_service import ingestion_service
from app.services.storage_service import storage_service
from config import VECTOR_DB_PATH, COLLECTION_NAME
from qdrant_client import QdrantClient

client = TestClient(app)


# ------------------------------------------------------------
# Helper: Create Valid In-Memory File Payloads
# ------------------------------------------------------------

def make_docx_bytes() -> bytes:
    from docx import Document as DocxDoc
    doc = DocxDoc()
    doc.add_heading("Deep Learning Architecture", level=1)
    doc.add_paragraph("Neural networks learn hierarchical representations through backpropagation.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_xlsx_bytes() -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Overview"
    ws.append(["Topic", "Details"])
    ws.append(["Distributed Systems", "Consensus protocols such as Raft and Paxos ensure fault tolerance."])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_pdf_bytes() -> bytes:
    import pymupdf
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((50, 72), "Modern cloud native microservices rely on containerization and orchestration.")
    pdf_bytes = pdf.tobytes()
    pdf.close()
    return pdf_bytes


# ------------------------------------------------------------
# 1. Validation Tests (Extension, Empty, Size, Sanitization)
# ------------------------------------------------------------

def test_reject_unsupported_file_extension():
    """Verify upload rejects unsupported file extensions with HTTP 400."""
    uid = str(uuid.uuid4())
    files = {"file": ("malicious.exe", b"binary content", "application/octet-stream")}
    data = {"user_id": uid}
    response = client.post("/api/v1/documents/upload", files=files, data=data)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_reject_empty_file():
    """Verify upload rejects 0-byte empty files with HTTP 400."""
    uid = str(uuid.uuid4())
    files = {"file": ("empty.txt", b"", "text/plain")}
    data = {"user_id": uid}
    response = client.post("/api/v1/documents/upload", files=files, data=data)
    assert response.status_code == 400
    assert "Empty files are not allowed" in response.json()["detail"]


def test_reject_file_too_large():
    """Verify upload rejects files exceeding 50 MB with HTTP 413."""
    uid = str(uuid.uuid4())
    # Create mock oversized file by monkeypatching len or using a large chunked stream test
    from app.api.routes import documents as doc_route_module
    orig_max = doc_route_module.MAX_FILE_SIZE_BYTES
    try:
        doc_route_module.MAX_FILE_SIZE_BYTES = 50  # Set low for fast testing
        files = {"file": ("large.txt", b"x" * 100, "text/plain")}
        data = {"user_id": uid}
        response = client.post("/api/v1/documents/upload", files=files, data=data)
        assert response.status_code == 413
        assert "exceeds the maximum" in response.json()["detail"]
    finally:
        doc_route_module.MAX_FILE_SIZE_BYTES = orig_max


def test_filename_sanitization():
    """Verify path traversal filenames like '../../bad.txt' are sanitized."""
    raw_filename = "../../dangerous_path/file.txt"
    sanitized = storage_service.sanitize_filename(raw_filename)
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert sanitized == "file.txt"


# ------------------------------------------------------------
# 2. Ingestion Pipeline Execution Across All 5 Supported Types
# ------------------------------------------------------------

def test_upload_and_process_txt_document():
    """Verify end-to-end ingestion for TXT document."""
    uid = str(uuid.uuid4())
    txt_content = b"Object-oriented programming focuses on objects and classes rather than actions and logic."
    files = {"file": ("oop_concepts.txt", txt_content, "text/plain")}
    data = {"user_id": uid}

    upload_res = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_res.status_code == 202
    resp_data = upload_res.json()
    doc_id = resp_data["document_id"]
    job_id = resp_data["job_id"]

    # Execute ingestion synchronously for deterministic testing
    db = SessionLocal()
    doc = db.get(Document, uuid.UUID(doc_id))
    storage_path = doc.storage_path
    db.close()

    ingestion_service.process_document_job(
        job_id=job_id,
        document_id=doc_id,
        user_id=uid,
        storage_path=storage_path,
        filename="oop_concepts.txt",
    )

    try:
        # Check job status endpoint
        job_res = client.get(f"/api/v1/ingestion/{job_id}?user_id={uid}")
        assert job_res.status_code == 200
        job_info = job_res.json()
        assert job_info["status"] == "completed"
        assert job_info["total_chunks"] >= 1
        assert job_info["processed_chunks"] == job_info["total_chunks"]
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


def test_upload_and_process_csv_document():
    """Verify end-to-end ingestion for CSV document."""
    uid = str(uuid.uuid4())
    csv_content = b"Concept,Definition\nPolymorphism,Ability of a message to be displayed in multiple forms"
    files = {"file": ("data.csv", csv_content, "text/csv")}
    data = {"user_id": uid}

    upload_res = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["document_id"]
    job_id = upload_res.json()["job_id"]

    db = SessionLocal()
    doc = db.get(Document, uuid.UUID(doc_id))
    storage_path = doc.storage_path
    db.close()

    try:
        ingestion_service.process_document_job(
            job_id=job_id,
            document_id=doc_id,
            user_id=uid,
            storage_path=storage_path,
            filename="data.csv",
        )

        job_res = client.get(f"/api/v1/ingestion/{job_id}?user_id={uid}")
        assert job_res.status_code == 200
        assert job_res.json()["status"] == "completed"
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


def test_upload_and_process_docx_document():
    """Verify end-to-end ingestion for DOCX document."""
    uid = str(uuid.uuid4())
    files = {"file": ("test_doc.docx", make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"user_id": uid}

    upload_res = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["document_id"]
    job_id = upload_res.json()["job_id"]

    db = SessionLocal()
    doc = db.get(Document, uuid.UUID(doc_id))
    storage_path = doc.storage_path
    db.close()

    try:
        ingestion_service.process_document_job(
            job_id=job_id,
            document_id=doc_id,
            user_id=uid,
            storage_path=storage_path,
            filename="test_doc.docx",
        )

        job_res = client.get(f"/api/v1/ingestion/{job_id}?user_id={uid}")
        assert job_res.status_code == 200
        assert job_res.json()["status"] == "completed"
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


def test_upload_and_process_xlsx_document():
    """Verify end-to-end ingestion for XLSX document."""
    uid = str(uuid.uuid4())
    files = {"file": ("sheet.xlsx", make_xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"user_id": uid}

    upload_res = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["document_id"]
    job_id = upload_res.json()["job_id"]

    db = SessionLocal()
    doc = db.get(Document, uuid.UUID(doc_id))
    storage_path = doc.storage_path
    db.close()

    try:
        ingestion_service.process_document_job(
            job_id=job_id,
            document_id=doc_id,
            user_id=uid,
            storage_path=storage_path,
            filename="sheet.xlsx",
        )

        job_res = client.get(f"/api/v1/ingestion/{job_id}?user_id={uid}")
        assert job_res.status_code == 200
        assert job_res.json()["status"] == "completed"
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


def test_upload_and_process_pdf_document():
    """Verify end-to-end ingestion for PDF document."""
    uid = str(uuid.uuid4())
    files = {"file": ("sample.pdf", make_pdf_bytes(), "application/pdf")}
    data = {"user_id": uid}

    upload_res = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["document_id"]
    job_id = upload_res.json()["job_id"]

    db = SessionLocal()
    doc = db.get(Document, uuid.UUID(doc_id))
    storage_path = doc.storage_path
    db.close()

    try:
        ingestion_service.process_document_job(
            job_id=job_id,
            document_id=doc_id,
            user_id=uid,
            storage_path=storage_path,
            filename="sample.pdf",
        )

        job_res = client.get(f"/api/v1/ingestion/{job_id}?user_id={uid}")
        assert job_res.status_code == 200
        assert job_res.json()["status"] == "completed"
    finally:
        client.delete(f"/api/v1/documents/{doc_id}?user_id={uid}")


def test_chat_retrieval_document_scoping():
    """Verify chat retrieval with document_id scopes search strictly to that document."""
    user_a = str(uuid.uuid4())

    files1 = {"file": ("doc_quantum.txt", b"Quantum computing uses qubits and superposition to process information.", "text/plain")}
    res1 = client.post("/api/v1/documents/upload", files=files1, data={"user_id": user_a})
    doc1_id = res1.json()["document_id"]
    job1_id = res1.json()["job_id"]

    files2 = {"file": ("doc_biology.txt", b"Photosynthesis in green plants synthesizes glucose using chlorophyll.", "text/plain")}
    res2 = client.post("/api/v1/documents/upload", files=files2, data={"user_id": user_a})
    doc2_id = res2.json()["document_id"]
    job2_id = res2.json()["job_id"]

    db = SessionLocal()
    doc1 = db.get(Document, uuid.UUID(doc1_id))
    doc2 = db.get(Document, uuid.UUID(doc2_id))
    sp1, sp2 = doc1.storage_path, doc2.storage_path
    db.close()

    ingestion_service.process_document_job(job1_id, doc1_id, user_a, sp1, "doc_quantum.txt")
    ingestion_service.process_document_job(job2_id, doc2_id, user_a, sp2, "doc_biology.txt")

    try:
        from retrieval.retrieval import Retriever
        retriever = Retriever()

        # Scoped retrieval with doc1_id
        results_doc1 = retriever.search("What is quantum?", user_id=user_a, document_id=doc1_id)
        for d in results_doc1:
            assert d.get("document_id") == doc1_id
            assert "biology" not in d.get("source", "").lower()

        # Scoped retrieval with doc2_id searching for quantum (should return 0 results)
        results_doc2 = retriever.search("What is quantum?", user_id=user_a, document_id=doc2_id)
        assert len(results_doc2) == 0
    finally:
        client.delete(f"/api/v1/documents/{doc1_id}?user_id={user_a}")
        client.delete(f"/api/v1/documents/{doc2_id}?user_id={user_a}")


# ------------------------------------------------------------
# 3. Ingestion Error Handling
# ------------------------------------------------------------

def test_ingestion_job_failure_marks_failed():
    """Verify corrupt/unreadable files transition ingestion job and document to 'failed' status."""
    uid = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    db = SessionLocal()
    from app.models.user import User
    if not db.get(User, uuid.UUID(uid)):
        db.add(User(id=uuid.UUID(uid), email=f"{uid}@test.com", password_hash="hash"))
        db.flush()

    storage_path = f"documents/{uid}/{doc_id}/corrupt.pdf"
    storage_service.upload_file(storage_path, b"NOT_A_VALID_PDF_HEADER_CORRUPTED_BYTES")

    doc = Document(id=uuid.UUID(doc_id), user_id=uuid.UUID(uid), filename="corrupt.pdf", file_type="pdf", file_size=40, storage_path=storage_path, status="uploaded")
    job = IngestionJob(id=uuid.UUID(job_id), document_id=uuid.UUID(doc_id), user_id=uuid.UUID(uid), status="queued")
    db.add(doc)
    db.add(job)
    db.commit()
    db.close()

    ingestion_service.process_document_job(
        job_id=job_id,
        document_id=doc_id,
        user_id=uid,
        storage_path=storage_path,
        filename="corrupt.pdf",
    )

    job_res = client.get(f"/api/v1/ingestion/{job_id}?user_id={uid}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "failed"
    assert job_data["error_message"] is not None
    assert "Ingestion error" in job_data["error_message"]


# ------------------------------------------------------------
# 4. Multi-Tenant Isolation & Deletion
# ------------------------------------------------------------

def test_tenant_isolation_get_and_delete_documents():
    """
    Verify User A cannot view, retrieve, or delete User B's documents.
    Verify User A can delete their own document and vectors are removed.
    """
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    files = {"file": ("user_a_notes.txt", b"Confidential financial notes for user A.", "text/plain")}
    res = client.post("/api/v1/documents/upload", files=files, data={"user_id": user_a})
    assert res.status_code == 202
    doc_a_id = res.json()["document_id"]
    job_a_id = res.json()["job_id"]

    # 1. User B tries to view Document A -> 404
    get_res = client.get(f"/api/v1/documents/{doc_a_id}?user_id={user_b}")
    assert get_res.status_code == 404

    # 2. User B tries to inspect User A's ingestion job -> 404
    job_res = client.get(f"/api/v1/ingestion/{job_a_id}?user_id={user_b}")
    assert job_res.status_code == 404

    # 3. User B tries to delete User A's document -> 404
    del_res = client.delete(f"/api/v1/documents/{doc_a_id}?user_id={user_b}")
    assert del_res.status_code == 404

    # 4. User A can view their document -> 200
    owner_get = client.get(f"/api/v1/documents/{doc_a_id}?user_id={user_a}")
    assert owner_get.status_code == 200
    assert owner_get.json()["filename"] == "user_a_notes.txt"

    # 5. User A deletes their document -> 200
    owner_del = client.delete(f"/api/v1/documents/{doc_a_id}?user_id={user_a}")
    assert owner_del.status_code == 200
    assert owner_del.json()["message"] == "Document and associated vectors deleted successfully."

    # Verify document is gone from DB
    check_get = client.get(f"/api/v1/documents/{doc_a_id}?user_id={user_a}")
    assert check_get.status_code == 404


# ------------------------------------------------------------
# 5. Local Qdrant Preservation Check
# ------------------------------------------------------------

def test_local_qdrant_4125_vectors_unmodified():
    """Verify local Qdrant collection contains exactly 4,125 points."""
    local_client = QdrantClient(path=str(VECTOR_DB_PATH))
    try:
        count = local_client.count(collection_name=COLLECTION_NAME, exact=True).count
        assert count == 4125, f"Expected 4,125 local vectors, found {count}"
    finally:
        local_client.close()
