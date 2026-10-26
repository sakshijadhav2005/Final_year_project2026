"""Regression tests for bugs fixed during the project review."""

import uuid

from app.graphs.state import merge_generated
from app.main import app
from fastapi.testclient import TestClient

SAMPLE = (
    b"Speaker 1: Welcome to the EventAI meetup on intelligent content operations. "
    b"Today we discuss multi-agent pipelines, guardrails and human review. "
    b"Speaker 2: Grounding every claim in the transcript keeps generated posts honest."
)


def _register(client: TestClient, role: str = "event_organizer") -> dict[str, str]:
    email = f"{role}_{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "role": role},
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_event(client: TestClient, headers: dict[str, str]) -> str:
    res = client.post(
        "/api/v1/events",
        headers=headers,
        json={"name": "Regression Meetup", "date": "2026-10-20", "type": "meetup"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _upload(client, headers, *, types: str, languages: str = "en", event_id: str | None = None):
    data = {"consent_confirmed": "true", "requested_types": types, "target_languages": languages}
    if event_id:
        data["event_id"] = event_id
    res = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("session.txt", SAMPLE, "text/plain")},
        data=data,
    )
    assert res.status_code == 202, res.text
    return res.json()


def test_merge_generated_keeps_one_piece_per_type() -> None:
    first = [{"type": "blog", "body": "v1"}, {"type": "summary", "body": "s"}]
    merged = merge_generated(first, [{"type": "blog", "body": "v2"}])
    assert len(merged) == 2
    assert {p["type"]: p["body"] for p in merged}["blog"] == "v2"


def test_all_six_formats_and_translations_without_duplicates() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        job = _upload(
            client,
            headers,
            types="summary,blog,linkedin,newsletter,ig_caption,flyer",
            languages="en,hi",
        )
        content = client.get(f"/api/v1/jobs/{job['id']}/content", headers=headers).json()
        english = [c for c in content if c["language"] == "en"]
        hindi = [c for c in content if c["language"] == "hi"]
        assert sorted(c["type"] for c in english) == sorted(
            ["summary", "blog", "linkedin", "newsletter", "instagram", "flyer"]
        )
        assert len(hindi) == len(english) == 6


def test_instagram_alias_is_generated() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        job = _upload(client, headers, types="instagram")
        content = client.get(f"/api/v1/jobs/{job['id']}/content", headers=headers).json()
        assert [c["type"] for c in content] == ["instagram"]


def test_job_exposes_owner_and_event() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        event_id = _create_event(client, headers)
        job = _upload(client, headers, types="summary", event_id=event_id)
        assert job["event_id"] == event_id
        assert job["user_id"]
        listed = client.get("/api/v1/jobs", headers=headers).json()
        assert any(j["id"] == job["id"] and j["event_id"] == event_id for j in listed)


def test_upload_rejects_unknown_event() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        res = client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("session.txt", SAMPLE, "text/plain")},
            data={"consent_confirmed": "true", "event_id": str(uuid.uuid4())},
        )
        assert res.status_code == 404


def test_download_endpoint_formats() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        job = _upload(client, headers, types="blog")
        piece = client.get(f"/api/v1/jobs/{job['id']}/content", headers=headers).json()[0]
        for fmt, mime in (("markdown", "text/markdown"), ("text", "text/plain"), ("json", "application/json")):
            res = client.get(
                f"/api/v1/content/{piece['id']}/download", params={"format": fmt}, headers=headers
            )
            assert res.status_code == 200, (fmt, res.text)
            assert res.headers["content-type"].startswith(mime)
            assert "attachment" in res.headers["content-disposition"]


def test_drafts_are_private_and_posts_are_owner_only() -> None:
    with TestClient(app) as client:
        owner = _register(client)
        other = _register(client, role="regular_user")
        job = _upload(client, owner, types="summary")
        draft = client.get(f"/api/v1/jobs/{job['id']}/content", headers=owner).json()[0]

        # Another user can't see, edit or approve someone else's unapproved draft.
        feed = client.get("/api/v1/content", headers=other).json()
        assert draft["id"] not in {c["id"] for c in feed}
        assert client.get(f"/api/v1/content/{draft['id']}", headers=other).status_code == 404
        assert (
            client.post(f"/api/v1/content/{draft['id']}/approve", headers=other).status_code == 404
        )

        # After the owner approves it, it becomes publicly readable but still not editable.
        assert client.post(f"/api/v1/content/{draft['id']}/approve", headers=owner).status_code == 200
        assert client.get(f"/api/v1/content/{draft['id']}", headers=other).status_code == 200
        assert (
            client.patch(
                f"/api/v1/content/{draft['id']}", headers=other, json={"body": "hacked"}
            ).status_code
            == 404
        )

        # Community posts: only the author may edit; approving one no longer crashes.
        post = client.post(
            "/api/v1/content", headers=other, json={"title": "My takeaway", "body": "Great talk"}
        )
        assert post.status_code == 201, post.text
        post_id = post.json()["id"]
        assert post.json()["job_id"] is None
        assert (
            client.patch(f"/api/v1/content/{post_id}", headers=owner, json={"body": "x"}).status_code
            == 404
        )
        assert client.post(f"/api/v1/content/{post_id}/approve", headers=other).status_code == 200


def test_chat_stream_without_session_uses_transcript() -> None:
    with TestClient(app) as client:
        headers = _register(client)
        job = _upload(client, headers, types="summary")
        # The React widgets send context_type + job_id and no session_id.
        res = client.post(
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "session_id": None,
                "message": "What was discussed?",
                "context_type": "organizer_copilot",
                "job_id": job["id"],
            },
        )
        assert res.status_code == 200, res.text
        assert '"session_id"' in res.text
        sessions = client.get("/api/v1/chat/sessions", headers=headers).json()
        assert len(sessions) == 1
        session_id = sessions[0]["id"]
        assert sessions[0]["persona"] == "organizer_copilot"

        follow_up = client.post(
            "/api/v1/chat/stream",
            headers=headers,
            json={"session_id": session_id, "message": "And the next steps?"},
        )
        assert follow_up.status_code == 200
        detail = client.get(f"/api/v1/chat/sessions/{session_id}", headers=headers).json()
        assert len(detail["messages"]) == 4  # two user + two assistant messages


def test_transcript_lookup_for_chat_grounding() -> None:
    import asyncio

    from app.api.v1.chat import _load_transcript_text
    from app.db.session import SessionLocal
    from app.models.user import User

    with TestClient(app) as client:
        headers = _register(client)
        event_id = _create_event(client, headers)
        job = _upload(client, headers, types="summary", event_id=event_id)
        me = client.get("/api/v1/auth/me", headers=headers).json()

    async def _lookup():
        async with SessionLocal() as db:
            user = await db.get(User, uuid.UUID(me["id"]))
            by_job = await _load_transcript_text(db, user, uuid.UUID(job["id"]), None)
            by_event = await _load_transcript_text(db, user, None, uuid.UUID(event_id))
            return by_job, by_event

    by_job, by_event = asyncio.run(_lookup())
    assert by_job and "EventAI meetup" in by_job
    assert by_event == by_job


def test_regenerate_works_without_transcript() -> None:
    import asyncio

    from app.db.session import SessionLocal
    from app.models.job import Transcript
    from sqlalchemy import delete

    with TestClient(app) as client:
        headers = _register(client)
        job = _upload(client, headers, types="summary")

        async def _drop_transcript():
            async with SessionLocal() as db:
                await db.execute(delete(Transcript).where(Transcript.job_id == uuid.UUID(job["id"])))
                await db.commit()

        asyncio.run(_drop_transcript())
        res = client.post(f"/api/v1/jobs/{job['id']}/regenerate", headers=headers, json={})
        assert res.status_code == 202, res.text
        final = client.get(f"/api/v1/jobs/{job['id']}", headers=headers).json()
        assert final["status"] in {"pending_review", "needs_review"}


def test_recover_interrupted_jobs_marks_them_failed() -> None:
    import asyncio

    from app.db.session import SessionLocal
    from app.models.job import Job
    from app.services.job_runner import recover_interrupted_jobs
    from sqlalchemy import update

    with TestClient(app) as client:
        headers = _register(client)
        job = _upload(client, headers, types="summary")

    async def _simulate_crash_and_recover():
        async with SessionLocal() as db:
            await db.execute(
                update(Job).where(Job.id == uuid.UUID(job["id"])).values(status="transcribing")
            )
            await db.commit()
        await recover_interrupted_jobs()
        async with SessionLocal() as db:
            return await db.get(Job, uuid.UUID(job["id"]))

    row = asyncio.run(_simulate_crash_and_recover())
    assert row.status == "failed"
    assert row.error_code == "interrupted"
