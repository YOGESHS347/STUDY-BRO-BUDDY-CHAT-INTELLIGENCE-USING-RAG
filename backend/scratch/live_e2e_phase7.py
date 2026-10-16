import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = BACKEND_DIR.parent / "document-intelligence-rag"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(RAG_DIR) not in sys.path:
    sys.path.append(str(RAG_DIR))

import time
import uuid
from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message

client = TestClient(app)

print("=" * 65)
print("LIVE END-TO-END VERIFICATION - PHASE 7 (CONVERSATIONS)")
print("=" * 65)

# -------------------------------------------------------------
# 0. Check Local Qdrant 4,125 Vectors Backup
# -------------------------------------------------------------
local_client = QdrantClient(path=str(RAG_DIR / "vector_db" / "qdrant"))
local_count = local_client.get_collection("documents").points_count
print(f"[STEP 0] Local Qdrant point count: {local_count}")
assert local_count == 4125, f"ERROR: Local database points count ({local_count}) != 4125"

# -------------------------------------------------------------
# 1. Health check
# -------------------------------------------------------------
res_health = client.get("/api/v1/health")
assert res_health.status_code == 200
health_data = res_health.json()
print(f"[STEP 1] Health Check: {health_data}")
assert health_data["database"] == "connected"

# -------------------------------------------------------------
# 2. Create Real Test Users via Supabase Auth Admin API
# -------------------------------------------------------------
print("\n[STEP 2] Creating Real Test Users via Supabase Auth Admin API...")
secret_key = settings.effective_service_role_key
assert secret_key, "SUPABASE_SECRET_KEY must be configured for Admin API"

admin_headers = {
    "apikey": secret_key,
    "Authorization": f"Bearer {secret_key}",
    "Content-Type": "application/json",
}

user_a_email = f"live_test_p7_a_{uuid.uuid4().hex[:8]}@example.com"
user_b_email = f"live_test_p7_b_{uuid.uuid4().hex[:8]}@example.com"
password = f"P@ssw0rd_{uuid.uuid4().hex[:12]}!"

user_a_id = None
user_b_id = None
token_a = None
token_b = None

try:
    with httpx.Client(timeout=30.0) as http:
        # Create User A
        res_a = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users",
            headers=admin_headers,
            json={"email": user_a_email, "password": password, "email_confirm": True},
        )
        assert res_a.status_code in (200, 201), f"Failed to create User A: {res_a.text}"
        user_a_id = res_a.json()["id"]
        print(f"         Created Supabase User A: {user_a_id}")

        # Create User B
        res_b = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users",
            headers=admin_headers,
            json={"email": user_b_email, "password": password, "email_confirm": True},
        )
        assert res_b.status_code in (200, 201), f"Failed to create User B: {res_b.text}"
        user_b_id = res_b.json()["id"]
        print(f"         Created Supabase User B: {user_b_id}")

        # Sign in User A -> Real ES256 Token
        login_res_a = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_PUBLISHABLE_KEY or secret_key},
            json={"email": user_a_email, "password": password},
        )
        assert login_res_a.status_code == 200, f"User A sign-in failed: {login_res_a.text}"
        token_a = login_res_a.json()["access_token"]
        print("         Obtained live ES256 Supabase JWT for User A")

        # Sign in User B -> Real ES256 Token
        login_res_b = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_PUBLISHABLE_KEY or secret_key},
            json={"email": user_b_email, "password": password},
        )
        assert login_res_b.status_code == 200, f"User B sign-in failed: {login_res_b.text}"
        token_b = login_res_b.json()["access_token"]
        print("         Obtained live ES256 Supabase JWT for User B")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # -------------------------------------------------------------
    # 3. User A creates Conversation
    # -------------------------------------------------------------
    print("\n[STEP 3] User A creating Conversation...")
    create_res = client.post("/api/v1/conversations", json={"title": "New Conversation"}, headers=headers_a)
    assert create_res.status_code == 201, f"Failed: {create_res.text}"
    conv_a = create_res.json()
    conv_a_id = conv_a["id"]
    print(f"         Created Conversation: id={conv_a_id}, title='{conv_a['title']}'")
    assert conv_a["user_id"] == user_a_id

    # -------------------------------------------------------------
    # 4. User A sends message before uploading documents -> Missing context behavior
    # -------------------------------------------------------------
    print("\n[STEP 4] User A sending message without documents: 'What is OOPS?'...")
    t0 = time.time()
    msg_res = client.post(
        f"/api/v1/conversations/{conv_a_id}/messages",
        json={"content": "What is OOPS?"},
        headers=headers_a,
    )
    elapsed = time.time() - t0
    assert msg_res.status_code == 200, f"Failed: {msg_res.text}"
    msg_data = msg_res.json()
    print(f"         RAG execution took {elapsed:.2f}s")
    print(f"         User Message:      '{msg_data['user_message']['content']}'")
    print(f"         Assistant Answer:  '{msg_data['assistant_message']['content'][:100]}...'")
    print(f"         Citations count:   {len(msg_data['sources'])} sources (Expected 0 for cold user)")

    assert msg_data["user_message"]["role"] == "user"
    assert msg_data["assistant_message"]["role"] == "assistant"
    assert "not contain enough information" in msg_data["assistant_message"]["content"].lower()
    assert len(msg_data["sources"]) == 0

    # -------------------------------------------------------------
    # 4b. User A uploads a document and asks follow-up -> Grounded answer with citations
    # -------------------------------------------------------------
    print("\n[STEP 4b] User A uploads 'oops_guide.txt' to test grounded citations...")
    doc_content = b"Object-Oriented Programming System (OOPS) is a programming paradigm based on objects and classes. The four main pillars of OOPS are Inheritance, Polymorphism, Encapsulation, and Abstraction."
    up_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("oops_guide.txt", doc_content, "text/plain")},
        headers=headers_a,
    )
    assert up_res.status_code == 202
    doc_id = up_res.json()["document_id"]
    job_id = up_res.json()["job_id"]
    print(f"         Document uploaded: {doc_id}, Job: {job_id}")

    # Wait for ingestion to complete
    for _ in range(15):
        time.sleep(1.0)
        job_res = client.get(f"/api/v1/ingestion/{job_id}", headers=headers_a).json()
        if job_res["status"] == "completed":
            print(f"         Ingestion completed in Qdrant Cloud ({job_res['total_chunks']} chunks)")
            break

    print("         User A sending follow-up: 'What are the four pillars of OOPS?'...")
    from unittest.mock import patch
    from app.services.rag_service import rag_service
    with patch.object(rag_service.get_generator(), "generate", return_value="Object-Oriented Programming System (OOPS) is structured around four pillars: Inheritance, Polymorphism, Encapsulation, and Abstraction."):
        msg_res2 = client.post(
            f"/api/v1/conversations/{conv_a_id}/messages",
            json={"content": "What are the four pillars of OOPS?"},
            headers=headers_a,
        )
        assert msg_res2.status_code == 200
        msg_data2 = msg_res2.json()
        print(f"         Follow-up User Msg:     '{msg_data2['user_message']['content']}'")
        print(f"         Follow-up Assistant:    '{msg_data2['assistant_message']['content'][:120]}...'")
        print(f"         Follow-up Citations:    {len(msg_data2['sources'])} sources")
        for s in msg_data2["sources"]:
            print(f"           - {s['source']} (Page {s['page']}, Score: {s['score']})")

        assert len(msg_data2["sources"]) > 0

    # Clean up uploaded document
    client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
    print("         Cleaned up User A's test document.")

    # -------------------------------------------------------------
    # 5. Verify conversation title was updated deterministically
    # -------------------------------------------------------------
    conv_a_updated = client.get(f"/api/v1/conversations/{conv_a_id}", headers=headers_a).json()
    print(f"\n[STEP 5] Updated Conversation Title: '{conv_a_updated['title']}'")
    assert conv_a_updated["title"] == "What is OOPS?"

    # -------------------------------------------------------------
    # 6. Verify chronological message history
    # -------------------------------------------------------------

    history_res = client.get(f"/api/v1/conversations/{conv_a_id}/messages", headers=headers_a)
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 4
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"
    assert history[3]["role"] == "assistant"

    # -------------------------------------------------------------
    # 7. Create second conversation for User A and verify ordering
    # -------------------------------------------------------------
    conv_a2 = client.post("/api/v1/conversations", json={"title": "Second Topic"}, headers=headers_a).json()
    list_a = client.get("/api/v1/conversations", headers=headers_a).json()
    print(f"\n[STEP 7] User A listed {len(list_a)} conversations (ordered updated_at DESC)")
    assert len(list_a) >= 2
    assert list_a[0]["updated_at"] >= list_a[1]["updated_at"]

    # -------------------------------------------------------------
    # 8-11. Cross-Tenant Security: User B vs User A
    # -------------------------------------------------------------
    print("\n[STEP 8-11] Testing Cross-Tenant Security Barriers...")
    cross_get = client.get(f"/api/v1/conversations/{conv_a_id}", headers=headers_b)
    print(f"         User B GET User A's conversation:  HTTP {cross_get.status_code} (Expected 404)")
    assert cross_get.status_code == 404

    cross_msgs = client.get(f"/api/v1/conversations/{conv_a_id}/messages", headers=headers_b)
    print(f"         User B GET User A's messages:      HTTP {cross_msgs.status_code} (Expected 404)")
    assert cross_msgs.status_code == 404

    cross_send = client.post(
        f"/api/v1/conversations/{conv_a_id}/messages",
        json={"content": "Unauthorized attack"},
        headers=headers_b,
    )
    print(f"         User B POST User A's messages:     HTTP {cross_send.status_code} (Expected 404)")
    assert cross_send.status_code == 404

    cross_del = client.delete(f"/api/v1/conversations/{conv_a_id}", headers=headers_b)
    print(f"         User B DELETE User A's conversation: HTTP {cross_del.status_code} (Expected 404)")
    assert cross_del.status_code == 404

    # -------------------------------------------------------------
    # 12. User A deletes Conversation A & verify cascading deletion
    # -------------------------------------------------------------
    print("\n[STEP 12] Deleting Conversation A and verifying cascading cleanup...")
    del_res = client.delete(f"/api/v1/conversations/{conv_a_id}", headers=headers_a)
    assert del_res.status_code == 200
    print(f"         Owner DELETE response: HTTP {del_res.status_code}")

    with SessionLocal() as db:
        remaining_msgs = db.query(Message).filter(Message.conversation_id == uuid.UUID(conv_a_id)).all()
        assert len(remaining_msgs) == 0
        print("         Verified cascading deletion of conversation messages in DB: 0 remaining.")

    # Clean up second conversation
    client.delete(f"/api/v1/conversations/{conv_a2['id']}", headers=headers_a)

    # -------------------------------------------------------------
    # 13. Verify local Qdrant collection point count
    # -------------------------------------------------------------
    local_count_end = local_client.get_collection("documents").points_count
    print(f"\n[STEP 13] Final Local Qdrant point count: {local_count_end}")
    assert local_count_end == 4125, f"ERROR: Local database points count ({local_count_end}) != 4125"
    print("         Verified local 4,125 vectors unmodified.")

finally:
    # -------------------------------------------------------------
    # Teardown: Delete Test Users from Supabase Auth
    # -------------------------------------------------------------
    print("\n[TEARDOWN] Cleaning up Supabase Auth test users...")
    with httpx.Client(timeout=30.0) as http:
        if user_a_id:
            del_a = http.delete(f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_a_id}", headers=admin_headers)
            print(f"         Cleaned up User A ({user_a_id}): HTTP {del_a.status_code}")
        if user_b_id:
            del_b = http.delete(f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_b_id}", headers=admin_headers)
            print(f"         Cleaned up User B ({user_b_id}): HTTP {del_b.status_code}")

print("\n" + "=" * 65)
print("ALL LIVE PHASE 7 E2E VERIFICATIONS PASSED SUCCESSFULLY!")
print("=" * 65)
