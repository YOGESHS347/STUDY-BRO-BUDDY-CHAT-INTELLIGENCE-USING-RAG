import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure paths are set
BACKEND_DIR = Path(r"C:\Users\yoges\OneDrive\Desktop\ragllm\backend")
RAG_DIR = Path(r"C:\Users\yoges\OneDrive\Desktop\ragllm\document-intelligence-rag")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(RAG_DIR) not in sys.path:
    sys.path.append(str(RAG_DIR))

from app.core.config import settings
from qdrant_client import QdrantClient

BASE_URL = "http://127.0.0.1:8000"


def print_step(name: str):
    print(f"\n{'=' * 60}\n[STEP] {name}\n{'=' * 60}")


def run_phase6_live_e2e():
    print_step("Phase 6 Live End-to-End Verification Starting")
    print(f"Supabase URL: {settings.SUPABASE_URL}")
    print(f"JWKS URL:     {settings.resolved_jwks_url}")
    print(f"Qdrant Cloud: {settings.QDRANT_URL}")

    # -------------------------------------------------------------
    # 0. Verify Local 4,125 Vector Database Integrity
    # -------------------------------------------------------------
    print_step("0. Check Local Qdrant 4,125 Vectors Backup")
    local_client = QdrantClient(path=str(RAG_DIR / "vector_db" / "qdrant"))
    local_count = local_client.get_collection("documents").points_count
    print(f"Local collection vector count: {local_count}")
    assert local_count == 4125, f"ERROR: Local database points count ({local_count}) != 4125"
    print("[OK] Local database intact at exactly 4,125 vectors.")

    # -------------------------------------------------------------
    # 1. Create Two Real Test Users via Supabase Admin API
    # -------------------------------------------------------------
    print_step("1. Create Test Users via Supabase Auth Admin API")
    secret_key = settings.effective_service_role_key
    assert secret_key, "SUPABASE_SECRET_KEY must be configured for Admin API"

    admin_headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    user_a_email = f"live_test_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"live_test_b_{uuid.uuid4().hex[:8]}@example.com"
    password = f"P@ssw0rd_{uuid.uuid4().hex[:12]}!"

    user_a_id = None
    user_b_id = None
    token_a = None
    token_b = None

    with httpx.Client(timeout=30.0) as http:
        # Create User A
        res_a = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users",
            headers=admin_headers,
            json={
                "email": user_a_email,
                "password": password,
                "email_confirm": True,
            },
        )
        assert res_a.status_code in (200, 201), f"Failed to create User A: {res_a.text}"
        user_a_id = res_a.json()["id"]
        print(f"✓ Created Supabase Test User A: {user_a_id} ({user_a_email})")

        # Create User B
        res_b = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users",
            headers=admin_headers,
            json={
                "email": user_b_email,
                "password": password,
                "email_confirm": True,
            },
        )
        assert res_b.status_code in (200, 201), f"Failed to create User B: {res_b.text}"
        user_b_id = res_b.json()["id"]
        print(f"✓ Created Supabase Test User B: {user_b_id} ({user_b_email})")

        # Sign in User A to get official ES256 Access Token
        login_res_a = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_PUBLISHABLE_KEY or secret_key},
            json={"email": user_a_email, "password": password},
        )
        assert login_res_a.status_code == 200, f"User A sign-in failed: {login_res_a.text}"
        token_a = login_res_a.json()["access_token"]
        print("✓ Obtained official asymmetric ES256 Supabase JWT for User A")

        # Sign in User B to get official ES256 Access Token
        login_res_b = http.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_PUBLISHABLE_KEY or secret_key},
            json={"email": user_b_email, "password": password},
        )
        assert login_res_b.status_code == 200, f"User B sign-in failed: {login_res_b.text}"
        token_b = login_res_b.json()["access_token"]
        print("✓ Obtained official asymmetric ES256 Supabase JWT for User B")

    try:
        # ---------------------------------------------------------
        # 2. Test FastAPI Backend Authentication with Live JWT
        # ---------------------------------------------------------
        from fastapi.testclient import TestClient
        from app.main import app

        # Test against real FastAPI app without conftest mocks
        client = TestClient(app)

        print_step("2. Test GET /api/v1/users/me with Live Token")
        me_res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token_a}"})
        assert me_res.status_code == 200, f"GET /users/me failed: {me_res.text}"
        me_data = me_res.json()
        assert me_data["id"] == user_a_id
        assert me_data["email"] == user_a_email
        assert "password" not in str(me_data).lower()
        print(f"✓ Authenticated profile verified for User A: id={me_data['id']}, email={me_data['email']}")

        # ---------------------------------------------------------
        # 3. Document Upload with Live Authenticated Token
        # ---------------------------------------------------------
        print_step("3. Test Document Upload with Live JWT")
        doc_content = b"Reinforcement learning uses reward signals to optimize decision policies over time."
        files = {"file": ("rl_notes.txt", doc_content, "text/plain")}
        upload_res = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert upload_res.status_code == 202, f"Upload failed: {upload_res.text}"
        upload_data = upload_res.json()
        doc_id = upload_data["document_id"]
        job_id = upload_data["job_id"]
        print(f"✓ Document uploaded: doc_id={doc_id}, job_id={job_id}")

        # ---------------------------------------------------------
        # 4. Multi-Tenant Cross-User Isolation Enforcement
        # ---------------------------------------------------------
        print_step("4. Test Cross-Tenant Access Controls")
        # User B cannot access User A's document download
        dl_b = client.get(
            f"/api/v1/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert dl_b.status_code == 404, f"Expected 404 for cross-user download, got {dl_b.status_code}"
        print("✓ User B cannot download User A's document (HTTP 404)")

        # User B cannot inspect User A's ingestion job
        job_b = client.get(
            f"/api/v1/ingestion/{job_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert job_b.status_code == 404, f"Expected 404 for cross-user job status, got {job_b.status_code}"
        print("✓ User B cannot inspect User A's ingestion job (HTTP 404)")

        # User B cannot delete User A's document
        del_b = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert del_b.status_code == 404, f"Expected 404 for cross-user delete, got {del_b.status_code}"
        print("✓ User B cannot delete User A's document (HTTP 404)")

        # User A can download their own document
        dl_a = client.get(
            f"/api/v1/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert dl_a.status_code == 200
        assert dl_a.content == doc_content
        print("✓ User A successfully downloaded their own document (HTTP 200)")

        # ---------------------------------------------------------
        # 5. Token Tampering & Security Boundaries
        # ---------------------------------------------------------
        print_step("5. Test Token Tampering & Security Rejections")
        # Missing Authorization header -> 401
        res_no_auth = client.get("/api/v1/users/me")
        assert res_no_auth.status_code == 401
        print("✓ Missing token rejected with HTTP 401")

        # Invalid scheme -> 401
        res_basic = client.get("/api/v1/users/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert res_basic.status_code == 401
        print("✓ Non-Bearer scheme rejected with HTTP 401")

        # Corrupted / tampered JWT -> 401
        tampered_token = token_a[:-6] + "xxxxxx"
        res_tampered = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res_tampered.status_code == 401
        print("✓ Tampered token rejected with HTTP 401")

        # Spoofed user_id in upload body -> 403 Forbidden
        files_spoof = {"file": ("spoof.txt", b"content", "text/plain")}
        res_spoof = client.post(
            "/api/v1/documents/upload",
            files=files_spoof,
            data={"user_id": user_b_id},  # User A authenticated, but supplies User B's ID in body
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_spoof.status_code == 403
        print("✓ Spoofed client user_id rejected with HTTP 403 Forbidden")

        # Clean up User A's document
        client.delete(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_a}"})
        print("✓ Cleaned up test document")

    finally:
        # ---------------------------------------------------------
        # 6. Delete Test Users via Supabase Admin API
        # ---------------------------------------------------------
        print_step("6. Clean Up Supabase Test Users via Admin API")
        with httpx.Client(timeout=30.0) as http:
            if user_a_id:
                http.delete(
                    f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_a_id}",
                    headers=admin_headers,
                )
                print(f"✓ Deleted User A ({user_a_id}) from Supabase Auth")
            if user_b_id:
                http.delete(
                    f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_b_id}",
                    headers=admin_headers,
                )
                print(f"✓ Deleted User B ({user_b_id}) from Supabase Auth")

    # -------------------------------------------------------------
    # 7. Final Verification of Local 4,125 Vectors
    # -------------------------------------------------------------
    print_step("7. Final Verification: Local 4,125 Vectors Intact")
    final_local_count = local_client.get_collection("documents").points_count
    assert final_local_count == 4125, f"Points changed: {final_local_count} != 4125"
    print(f"✓ Final check passed: exactly {final_local_count} local vectors intact.")
    print("\n🎉 ALL PHASE 6 LIVE END-TO-END VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_phase6_live_e2e()
