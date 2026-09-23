from app.main import app
from starlette.testclient import TestClient


def test_auth_profile_and_chat_flow():
    with TestClient(app) as client:
        email = "chat_user@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "role": "event_organizer"},
        )
        if reg.status_code == 201:
            token = reg.json()["access_token"]
        else:
            login = client.post(
                "/api/v1/auth/login", json={"email": email, "password": "password123"}
            )
            token = login.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Test Get & Update Profile
        prof = client.get("/api/v1/auth/profile", headers=headers)
        assert prof.status_code == 200

        updated_prof = client.put(
            "/api/v1/auth/profile",
            headers=headers,
            json={
                "full_name": "Dr. Sarah Chen",
                "organization": "CloudScale AI",
                "job_title": "Head of AI",
                "brand_tone": "authoritative_inspiring",
                "linkedin_handle": "sarahchen-ai",
            },
        )
        assert updated_prof.status_code == 200
        assert updated_prof.json()["full_name"] == "Dr. Sarah Chen"
        assert updated_prof.json()["organization"] == "CloudScale AI"

        # 2. Test Create Chat Session
        sess = client.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "Test Session", "persona": "organizer_copilot"},
        )
        assert sess.status_code == 201
        session_id = sess.json()["id"]

        # 3. Test List Sessions
        sessions_list = client.get("/api/v1/chat/sessions", headers=headers)
        assert sessions_list.status_code == 200
        assert len(sessions_list.json()) >= 1

        # 4. Test Stream Message
        stream_res = client.post(
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "session_id": session_id,
                "message": "What were the main highlights of this session?",
                "persona": "organizer_copilot",
            },
        )
        assert stream_res.status_code == 200
        assert "data: " in stream_res.text
