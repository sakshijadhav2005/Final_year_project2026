import uuid
from collections.abc import Generator

from app.main import app
from fastapi.testclient import TestClient


def test_root_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_api_v1_health() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200


def _client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


def test_register_login_and_me() -> None:

    email = f"org_{uuid.uuid4().hex[:8]}@example.com"
    with TestClient(app) as client:
        register = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "role": "event_organizer"},
        )
        assert register.status_code in {201, 409}
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == email


def test_upload_txt_generates_content() -> None:
    email = f"org_{uuid.uuid4().hex[:8]}@example.com"
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        if login.status_code != 200:
            client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "password123", "role": "event_organizer"},
            )
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "password123"},
            )
        token = login.json()["access_token"]
        files = {
            "file": (
                "session.txt",
                b"Welcome to the EventAI demo about recordings becoming blogs.",
                "text/plain",
            )
        }
        data = {
            "consent_confirmed": "true",
            "requested_types": "summary,blog,linkedin",
            "target_languages": "en",
        }
        upload = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert upload.status_code == 202, upload.text
        job_id = upload.json()["id"]
        job = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        assert job.status_code == 200
        assert job.json()["status"] in {"pending_review", "needs_review", "ready_to_publish"}
        content = client.get(
            f"/api/v1/jobs/{job_id}/content", headers={"Authorization": f"Bearer {token}"}
        )
        assert content.status_code == 200
        assert len(content.json()) >= 1
        first = content.json()[0]
        approved = client.post(
            f"/api/v1/content/{first['id']}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
