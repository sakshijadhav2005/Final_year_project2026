import uuid
from datetime import date
from fastapi.testclient import TestClient

from app.main import app


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
    filtered = client.get("/api/v1/events/?type=event", headers={"Authorization": f"Bearer {user_token}"})
    assert filtered.status_code == 200
    assert all(e["type"] == "event" for e in filtered.json())

    # 7. Get event by ID
    get_event = client.get(f"/api/v1/events/{event_id}", headers={"Authorization": f"Bearer {user_token}"})
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
    community_resp = client.get("/api/v1/content", headers={"Authorization": f"Bearer {user_token}"})
    assert community_resp.status_code == 200
    assert any(c["id"] == post_data["id"] for c in community_resp.json())
