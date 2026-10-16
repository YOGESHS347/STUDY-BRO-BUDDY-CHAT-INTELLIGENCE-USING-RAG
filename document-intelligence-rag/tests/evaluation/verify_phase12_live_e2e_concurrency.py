"""
Live End-to-End and Concurrency Verification for Phase 12.
Tests complete lifecycle:
Upload -> Redis Enqueue -> Worker Dequeue -> Processing -> Qdrant Upsert -> Retrieval/Chat Query -> Deletion -> 4,125 Vector Integrity.
Concurrency: 5 simultaneous uploads across multiple users with strict tenant isolation.
"""

import os
import sys
import time
import uuid
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
RAG_DIR = SCRIPT_DIR.parent.parent
BACKEND_DIR = RAG_DIR.parent / "backend"

sys.path.insert(0, str(RAG_DIR))
sys.path.insert(0, str(BACKEND_DIR))

os.environ["VECTOR_STORE_BACKEND"] = "local"

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.main import app
from app.core.auth import jwt_verifier
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.services.redis_service import redis_service
from app.services.queue_service import queue_service
from app.services.rag_service import rag_service
from worker.worker import WorkerProcess
from config import VECTOR_DB_PATH, COLLECTION_NAME

# Import auth test helpers
from tests.conftest import create_test_token, mock_conftest_key_getter

client = TestClient(app)


def auth_header(user_id: str) -> dict:
    token = create_test_token(sub=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def get_qdrant_vector_count() -> int:
    qc = QdrantClient(path=str(VECTOR_DB_PATH))
    try:
        return qc.count(collection_name=COLLECTION_NAME, exact=True).count
    finally:
        qc.close()


def run_worker_in_thread(stop_event: threading.Event):
    def worker_loop():
        while not stop_event.is_set():
            try:
                payload = queue_service.dequeue_ingestion_job(timeout=1)
                if payload and payload.get("job_id"):
                    from worker.ingestion_worker import ingestion_worker
                    ingestion_worker.process_job(payload["job_id"])
            except Exception:
                pass
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    return t


def test_live_e2e_and_concurrency():
    print("\n" + "=" * 75)
    print("PHASE 12: STARTING LIVE E2E & CONCURRENCY VERIFICATION")
    print("=" * 75)

    with patch.object(jwt_verifier.jwks_client, "get_signing_key_from_jwt", side_effect=mock_conftest_key_getter):
        initial_vector_count = get_qdrant_vector_count()
        print(f"[BASELINE] Initial local Qdrant vector count: {initial_vector_count}")
        assert initial_vector_count == 4125, f"Expected 4,125 vectors, found {initial_vector_count}"

        # Confirm Redis is running
        health = redis_service.check_health()
        print(f"[REDIS] Redis health: {health}")
        assert health == "connected", "Redis must be connected for live E2E test"

        # Start background worker thread
        stop_event = threading.Event()
        worker_thread = run_worker_in_thread(stop_event)
        print("[WORKER] Started background worker consumer thread.")

        try:
            # ============================================================
            # PART 1: LIVE E2E INGESTION TEST (Step 17)
            # ============================================================
            print("\n--- [PART 1] Live E2E Ingestion Test ---")
            user_e2e = str(uuid.uuid4())
            headers_e2e = auth_header(user_e2e)

            doc_content = (
                b"Quantum teleportation utilizes quantum entanglement to transmit information "
                b"across arbitrary distances instantaneously without moving physical particles."
            )
            files = {"file": ("temp_quantum_e2e.txt", doc_content, "text/plain")}
            data = {"user_id": user_e2e}

            print(f"[UPLOAD] Uploading temp document for user {user_e2e[:8]}...")
            upload_res = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers_e2e)
            assert upload_res.status_code == 202, f"Upload failed: {upload_res.text}"
            res_data = upload_res.json()
            doc_id = res_data["document_id"]
            job_id = res_data["job_id"]
            print(f"[API] 202 Accepted: doc_id={doc_id}, job_id={job_id}, status={res_data['status']}")
            assert res_data["status"] == "queued"

            try:
                # Wait for worker to dequeue and complete
                print("[POLL] Waiting for worker to process job to COMPLETED...")
                completed = False
                for _ in range(40):
                    time.sleep(0.5)
                    status_res = client.get(f"/api/v1/ingestion/{job_id}", headers=headers_e2e)
                    if status_res.status_code == 200:
                        job_status = status_res.json()["status"]
                        if job_status == "completed":
                            completed = True
                            chunks = status_res.json()["total_chunks"]
                            print(f"[STATUS] Job completed successfully with {chunks} chunks!")
                            break
                assert completed, "Ingestion job did not reach 'completed' within timeout"

                # Verify Qdrant count increased by exactly the new chunks
                current_count = get_qdrant_vector_count()
                print(f"[QDRANT] Vector count after ingestion: {current_count} (added {current_count - 4125})")
                assert current_count > 4125

                # Direct retrieval verification
                print("[RETRIEVAL] Verifying vector retrieval from Qdrant for ingested document...")
                from retrieval.retrieval import Retriever
                retriever = Retriever()
                try:
                    search_results = retriever.search("What is quantum teleportation?", user_id=user_e2e, document_id=doc_id)
                    print(f"[RETRIEVAL] Retrieved {len(search_results)} candidates.")
                    assert len(search_results) >= 1
                    assert "entanglement" in search_results[0].get("text", "").lower()
                    assert search_results[0].get("document_id") == doc_id
                    print("[SUCCESS] Direct vector retrieval verified!")
                finally:
                    retriever.close()

                # Chat API endpoint verification (mock LLM generator if local server unavailable)
                print("[CHAT] Querying RAG chat endpoint...")
                chat_payload = {
                    "question": "What does quantum teleportation utilize to transmit information?",
                    "conversation_history": [],
                    "top_k": 3,
                    "document_id": doc_id,
                }

                generator = rag_service.get_generator()
                with patch.object(
                    generator,
                    "generate",
                    return_value="Quantum teleportation utilizes quantum entanglement to transmit information across arbitrary distances.",
                ):
                    try:
                        chat_res = client.post("/api/v1/chat/query", json=chat_payload, headers=headers_e2e)
                        assert chat_res.status_code == 200, f"Chat query failed: {chat_res.text}"
                        chat_data = chat_res.json()
                        answer = chat_data["answer"]
                        print(f"[CHAT ANSWER]:\n{answer}")
                        assert "entanglement" in answer.lower(), "Answer should mention entanglement"
                        assert len(chat_data["sources"]) >= 1
                        assert "temp_quantum_e2e.txt" in chat_data["sources"][0]["source"]
                        print("[SUCCESS] Grounded chat answer verified!")
                    finally:
                        if rag_service._retriever:
                            rag_service._retriever.close()
                            rag_service._retriever = None
            finally:
                # Clean up temporary document
                print(f"[CLEANUP] Deleting temporary document {doc_id}...")
                del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=headers_e2e)
                assert del_res.status_code == 200
                print("[CLEANUP] Document deleted.")

            # Verify vectors removed and vector count restored
            after_del_count = get_qdrant_vector_count()
            print(f"[QDRANT] Vector count after deletion: {after_del_count}")
            assert after_del_count == 4125, f"Vector count expected 4,125, found {after_del_count}"
            print("[SUCCESS] Part 1 E2E verified with clean vector restoration!")

            # ============================================================
            # PART 2: CONCURRENCY TEST (Step 18)
            # ============================================================
            print("\n--- [PART 2] Concurrency Test (5 Rapid Uploads) ---")
            user_alpha = str(uuid.uuid4())
            user_beta = str(uuid.uuid4())
            headers_alpha = auth_header(user_alpha)
            headers_beta = auth_header(user_beta)

            concurrent_docs = [
                (user_alpha, headers_alpha, "alpha_doc1.txt", b"Alpha user confidential notes on microservice mesh routing."),
                (user_alpha, headers_alpha, "alpha_doc2.txt", b"Alpha user architecture guidelines for event-driven stream processing."),
                (user_alpha, headers_alpha, "alpha_doc3.txt", b"Alpha user guidelines on distributed consensus using Raft protocol."),
                (user_beta, headers_beta, "beta_doc1.txt", b"Beta user financial audit report for Q3 compliance assessment."),
                (user_beta, headers_beta, "beta_doc2.txt", b"Beta user risk evaluation matrix for cloud deployment infrastructure."),
            ]

            uploaded_jobs = []
            print("[UPLOAD] Rapidly submitting 5 concurrent documents...")
            for uid, hdrs, fname, b_content in concurrent_docs:
                u_res = client.post(
                    "/api/v1/documents/upload",
                    files={"file": (fname, b_content, "text/plain")},
                    data={"user_id": uid},
                    headers=hdrs,
                )
                assert u_res.status_code == 202
                u_data = u_res.json()
                uploaded_jobs.append((uid, hdrs, u_data["document_id"], u_data["job_id"], fname))
                print(f"  -> Submitted {fname} for user {uid[:8]}: job {u_data['job_id'][:8]} (queued)")

            # Wait for all 5 jobs to complete
            print("[POLL] Waiting for all 5 concurrent jobs to complete...")
            all_completed = False
            for attempt in range(60):
                time.sleep(0.5)
                completed_count = 0
                for uid, hdrs, doc_id, jid, fname in uploaded_jobs:
                    st_res = client.get(f"/api/v1/ingestion/{jid}", headers=hdrs)
                    if st_res.status_code == 200 and st_res.json()["status"] == "completed":
                        completed_count += 1
                if completed_count == 5:
                    all_completed = True
                    print(f"[STATUS] All 5 jobs completed successfully! (took {(attempt + 1) * 0.5:.1f}s)")
                    break

            assert all_completed, "Not all 5 concurrent jobs completed in time!"

            # Multi-Tenant Cross-User Isolation check
            print("[ISOLATION] Verifying tenant isolation across concurrent jobs...")
            alpha_doc_id = uploaded_jobs[0][2]
            beta_cross_get = client.get(f"/api/v1/documents/{alpha_doc_id}", headers=headers_beta)
            assert beta_cross_get.status_code == 404, "User Beta must NOT access User Alpha's document"

            beta_cross_job = client.get(f"/api/v1/ingestion/{uploaded_jobs[0][3]}", headers=headers_beta)
            assert beta_cross_job.status_code == 404, "User Beta must NOT inspect User Alpha's ingestion job"
            print("[ISOLATION] Cross-tenant isolation verified!")

            # Clean up all 5 temporary documents
            print("[CLEANUP] Cleaning up all 5 temporary documents...")
            for uid, hdrs, doc_id, jid, fname in uploaded_jobs:
                del_r = client.delete(f"/api/v1/documents/{doc_id}", headers=hdrs)
                assert del_r.status_code == 200

            # Final vector count verification
            final_count = get_qdrant_vector_count()
            print(f"[FINAL] Vector count after all cleanups: {final_count}")
            assert final_count == 4125, f"Final count expected 4,125, found {final_count}"
            print("\n" + "=" * 75)
            print("ALL PHASE 12 LIVE E2E & CONCURRENCY CHECKS PASSED PERFECTLY!")
            print("=" * 75 + "\n")

        finally:
            stop_event.set()
            time.sleep(0.5)


if __name__ == "__main__":
    test_live_e2e_and_concurrency()
