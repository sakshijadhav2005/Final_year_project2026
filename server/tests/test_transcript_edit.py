"""Human correction of the transcript (PATCH /jobs/{id}/transcript)."""

import uuid

from app.main import app
from fastapi.testclient import TestClient

SAMPLE = (
    b"Speaker 1: Welcome to the Event A I meetup on intelligent content operations. "
    b"Today we discuss multi-agent pipelines, guardrails and human review."
)


def _headers(client: TestClient) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"te_{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "role": "event_organizer",
        },
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _job(client: TestClient, headers: dict[str, str]) -> str:
    res = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("session.txt", SAMPLE, "text/plain")},
        data={"consent_confirmed": "true", "requested_types": "summary", "target_languages": "en"},
    )
    assert res.status_code == 202, res.text
    return res.json()["id"]


def test_edit_saves_text_marks_edited_and_regenerate_uses_it() -> None:
    with TestClient(app) as client:
        headers = _headers(client)
        job_id = _job(client, headers)
        before = client.get(f"/api/v1/jobs/{job_id}/transcript", headers=headers).json()
        assert before["edited"] is False

        fixed = before["full_text"].replace("Event A I", "EventAI")
        res = client.patch(
            f"/api/v1/jobs/{job_id}/transcript", headers=headers, json={"full_text": fixed}
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["full_text"] == fixed
        assert body["edited"] is True and body["edited_at"]
        # Timings from the recording are kept for the Sources panel.
        assert body["segments"] == before["segments"]

        again = client.get(f"/api/v1/jobs/{job_id}/transcript", headers=headers).json()
        assert again["full_text"] == fixed and again["edited"] is True

        regen = client.post(f"/api/v1/jobs/{job_id}/regenerate", headers=headers, json={})
        assert regen.status_code == 202, regen.text
        after = client.get(f"/api/v1/jobs/{job_id}/transcript", headers=headers).json()
        assert after["full_text"] == fixed  # not transcribed again
        assert client.get(f"/api/v1/jobs/{job_id}/content", headers=headers).json()


def test_empty_text_is_rejected() -> None:
    with TestClient(app) as client:
        headers = _headers(client)
        job_id = _job(client, headers)
        res = client.patch(
            f"/api/v1/jobs/{job_id}/transcript", headers=headers, json={"full_text": "   "}
        )
        assert res.status_code == 422


def test_other_users_cannot_edit() -> None:
    with TestClient(app) as client:
        owner = _headers(client)
        stranger = _headers(client)
        job_id = _job(client, owner)
        res = client.patch(
            f"/api/v1/jobs/{job_id}/transcript", headers=stranger, json={"full_text": "hijacked"}
        )
        assert res.status_code == 404
        text = client.get(f"/api/v1/jobs/{job_id}/transcript", headers=owner).json()["full_text"]
        assert text != "hijacked"
