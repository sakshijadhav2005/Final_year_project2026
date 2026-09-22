from fastapi.testclient import TestClient
import uuid

from app.main import app
from app.models.job import Job
from app.models.user import User


def get_auth_token(client: TestClient) -> str:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "role": "event_organizer"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return login.json()["access_token"]


def test_list_jobs_empty() -> None:
    with TestClient(app) as client:
        token = get_auth_token(client)
        resp = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == []


def test_unauthorized_access() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/jobs")
        # Should be 403 or 401 without token
        assert resp.status_code in [401, 403]


def test_get_nonexistent_job() -> None:
    with TestClient(app) as client:
        token = get_auth_token(client)
        fake_uuid = str(uuid.uuid4())
        resp = client.get(f"/api/v1/jobs/{fake_uuid}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404


def test_sse_query_token_auth() -> None:
    with TestClient(app) as client:
        token = get_auth_token(client)
        fake_uuid = str(uuid.uuid4())
        # Querying events with token query param should yield 404 for nonexistent job (authenticated), NOT 401 Unauthorized
        resp = client.get(f"/api/v1/jobs/{fake_uuid}/events?token={token}")
        assert resp.status_code == 404


def test_delete_job() -> None:
    with TestClient(app) as client:
        token = get_auth_token(client)
        # Create a test job via direct upload
        files = {
            "file": ("session.txt", b"Short test snippet for session deletion.", "text/plain")
        }
        data = {
            "consent_confirmed": "true",
            "requested_types": "summary",
            "target_languages": "en",
        }
        upload = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert upload.status_code == 202
        job_id = upload.json()["id"]

        # Delete the job
        del_resp = client.delete(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        assert del_resp.status_code == 204

        # Confirm job no longer exists
        get_resp = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_resp.status_code == 404


