import uuid
from datetime import date

from app.main import app
from fastapi.testclient import TestClient


def test_event_crud_and_role_guard():
    client = TestClient(app)

    # 1. Register event organizer
    org_email = f"org_{uuid.uuid4().hex[:8]}@example.com"
    reg_org = client.post(
        "/api/v1/auth/register",
        json={"email": org_email, "password": "password123", "role": "event_organizer"},
    )
    assert reg_org.status_code == 201
    org_token = reg_org.json()["access_token"]

    # 2. Register regular user
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    reg_user = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "password123", "role": "regular_user"},
    )
    assert reg_user.status_code == 201
    user_token = reg_user.json()["access_token"]

    # 3. Regular user attempting to create event -> 403 Forbidden
    forbidden_resp = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": "Unauthorized Meetup",
            "date": str(date.today()),
            "topic": "Testing RBAC",
            "type": "meetup",
        },
    )
    assert forbidden_resp.status_code == 403
    assert "Insufficient permissions" in forbidden_resp.json()["detail"]

    # 4. Organizer creating event -> 201 Created
    create_resp = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "name": "AI Tech Summit 2026",
            "date": str(date.today()),
            "topic": "Future of Generative Media",
            "organizer_name": "EventAI Organizer",
            "type": "event",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    event_data = create_resp.json()
    assert event_data["name"] == "AI Tech Summit 2026"
    assert event_data["type"] == "event"
    event_id = event_data["id"]

    # 5. List events (both users can view)
    list_org = client.get("/api/v1/events/", headers={"Authorization": f"Bearer {org_token}"})
    assert list_org.status_code == 200
    assert any(e["id"] == event_id for e in list_org.json())

    list_user = client.get("/api/v1/events/", headers={"Authorization": f"Bearer {user_token}"})
    assert list_user.status_code == 200
    assert any(e["id"] == event_id for e in list_user.json())

    # 6. Filter by type
    filtered = client.get(
        "/api/v1/events/?type=event", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert filtered.status_code == 200
    assert all(e["type"] == "event" for e in filtered.json())

    # 7. Get event by ID
    get_event = client.get(
        f"/api/v1/events/{event_id}", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert get_event.status_code == 200
    assert get_event.json()["id"] == event_id

    # 8. User creating community post
    post_resp = client.post(
        "/api/v1/content/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "title": "Excited for the AI Summit!",
            "body": "Looking forward to learning about video content transformation.",
            "event_id": event_id,
            "type": "user_post",
        },
    )
    assert post_resp.status_code == 201
    post_data = post_resp.json()
    assert post_data["title"] == "Excited for the AI Summit!"
    assert post_data["event_id"] == event_id

    # 9. List community content
    community_resp = client.get(
        "/api/v1/content", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert community_resp.status_code == 200
    assert any(c["id"] == post_data["id"] for c in community_resp.json())


def test_event_upload_association():
    from unittest.mock import patch

    client = TestClient(app)

    # 1. Register Organizer A
    org_a_email = f"org_a_{uuid.uuid4().hex[:8]}@example.com"
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": org_a_email, "password": "password123", "role": "event_organizer"},
    )
    assert reg_a.status_code == 201
    org_a_token = reg_a.json()["access_token"]

    # 2. Register Organizer B
    org_b_email = f"org_b_{uuid.uuid4().hex[:8]}@example.com"
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": org_b_email, "password": "password123", "role": "event_organizer"},
    )
    assert reg_b.status_code == 201
    org_b_token = reg_b.json()["access_token"]

    # 3. Register Admin
    admin_email = "admin@example.com"
    reg_admin = client.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "password": "password123", "role": "admin"},
    )
    if reg_admin.status_code == 201:
        admin_token = reg_admin.json()["access_token"]
    else:
        log_admin = client.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": "password123"},
        )
        admin_token = log_admin.json()["access_token"]

    # 4. Organizer A creates Event A
    create_resp = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_a_token}"},
        json={
            "name": "Organizer A Keynote",
            "date": str(date.today()),
            "topic": "Event to Recording Association",
            "type": "event",
        },
    )
    assert create_resp.status_code == 201
    event_a_id = create_resp.json()["id"]

    sample_file = ("speech.txt", b"Testing event recording association audio text.", "text/plain")

    with patch("app.api.v1.uploads.enqueue_process_job") as mock_enqueue:
        mock_enqueue.return_value = "mocked"

        # 5. Standalone upload without event_id -> success, event_id is None
        res_standalone = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {org_a_token}"},
            files={"file": sample_file},
            data={"consent_confirmed": "true"},
        )
        assert res_standalone.status_code == 202
        assert res_standalone.json()["event_id"] is None

        # 6. Upload with invalid UUID -> 400 Bad Request
        res_invalid_uuid = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {org_a_token}"},
            files={"file": sample_file},
            data={"consent_confirmed": "true", "event_id": "not-a-valid-uuid"},
        )
        assert res_invalid_uuid.status_code == 400
        assert "Invalid event_id UUID format" in str(res_invalid_uuid.json()["detail"])

        # 7. Upload with nonexistent event_id -> 404 Not Found
        random_uuid = str(uuid.uuid4())
        res_nonexistent = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {org_a_token}"},
            files={"file": sample_file},
            data={"consent_confirmed": "true", "event_id": random_uuid},
        )
        assert res_nonexistent.status_code == 404
        assert "Event not found" in str(res_nonexistent.json()["detail"])

        # 8. Organizer B tries to associate recording with Organizer A's event -> 403 Forbidden
        res_unauthorized = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {org_b_token}"},
            files={"file": sample_file},
            data={"consent_confirmed": "true", "event_id": event_a_id},
        )
        assert res_unauthorized.status_code == 403
        assert "not authorized" in str(res_unauthorized.json()["detail"]).lower()

        # 9. Authorized Organizer A associates recording with Event A -> 202 Accepted, event_id set
        res_authorized = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {org_a_token}"},
            files={"file": sample_file},
            data={"consent_confirmed": "true", "event_id": event_a_id},
        )
        assert res_authorized.status_code == 202
        job_data = res_authorized.json()
        assert job_data["event_id"] == event_a_id

        # 10. Admin can associate with Organizer A's event -> 202 Accepted
        res_admin = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": sample_file},
            data={"consent_confirmed": "true", "event_id": event_a_id},
        )
        assert res_admin.status_code == 202
        assert res_admin.json()["event_id"] == event_a_id
