"""Every user sees only their own sessions; admins see everyone's only when asking."""

import asyncio
import uuid
from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import update


def _user(client: TestClient, role: str = "event_organizer") -> tuple[dict, str]:
    email = f"iso_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "role": role})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def _make_admin(user_id: str) -> None:
    from app.db.session import SessionLocal
    from app.models.user import User

    async def go():
        async with SessionLocal() as db:
            await db.execute(update(User).where(User.id == uuid.UUID(user_id)).values(role="admin"))
            await db.commit()

    asyncio.run(go())


def _upload(client: TestClient, headers: dict) -> str:
    files = {"file": ("talk.txt", b"Speaker 1: Welcome to the session on agents.", "text/plain")}
    r = client.post(
        "/api/v1/uploads", headers=headers, files=files,
        data={"consent_confirmed": "true", "requested_types": "summary", "target_languages": "en"},
    )
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_sessions_are_private_to_their_owner_for_every_role():
    with patch("app.api.v1.uploads.enqueue_process_job", return_value="mocked"):
        with TestClient(app) as client:
            alice, _ = _user(client)
            bob, _ = _user(client)
            admin, admin_id = _user(client)
            _make_admin(admin_id)
            # admin needs a fresh token carrying the admin role
            a_job = _upload(client, alice)
            b_job = _upload(client, bob)

            assert [j["id"] for j in client.get("/api/v1/jobs", headers=alice).json()] == [a_job]
            assert [j["id"] for j in client.get("/api/v1/jobs", headers=bob).json()] == [b_job]
            # other people's sessions cannot be opened either
            assert client.get(f"/api/v1/jobs/{b_job}", headers=alice).status_code == 404
            assert client.get(f"/api/v1/jobs/{b_job}/transcript", headers=alice).status_code == 404
            assert client.get(f"/api/v1/jobs/{b_job}/content", headers=alice).status_code == 404
            assert client.delete(f"/api/v1/jobs/{b_job}", headers=alice).status_code == 404
            # a regular user cannot widen the scope
            assert [j["id"] for j in client.get("/api/v1/jobs?scope=all", headers=alice).json()] == [a_job]

            # admin: own (empty) dashboard by default, everything only on request
            assert client.get("/api/v1/jobs", headers=admin).json() == []
            all_ids = {j["id"] for j in client.get("/api/v1/jobs?scope=all", headers=admin).json()}
            assert {a_job, b_job} <= all_ids


def test_my_events_only_lists_own_events():
    with TestClient(app) as client:
        alice, _ = _user(client)
        bob, _ = _user(client)
        ev = {"date": "2026-10-20", "type": "meetup", "topic": "AI", "location": "Pune"}
        a = client.post("/api/v1/events", headers=alice, json={**ev, "name": "Alice meetup"}).json()["id"]
        b = client.post("/api/v1/events", headers=bob, json={**ev, "name": "Bob meetup"}).json()["id"]

        mine = {e["id"] for e in client.get("/api/v1/events?mine=true", headers=alice).json()}
        assert a in mine and b not in mine
        catalog = {e["id"] for e in client.get("/api/v1/events", headers=alice).json()}
        assert {a, b} <= catalog  # the public catalog still lists every event
