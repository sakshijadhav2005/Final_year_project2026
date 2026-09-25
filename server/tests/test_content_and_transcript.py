import uuid
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.job import Job, Transcript


def _register_user(client: TestClient, role: str) -> tuple[str, str]:
    email = f"{role}_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "role": role},
    )
    if reg.status_code == 201:
        data = reg.json()
        return data["access_token"], data["user"]["id"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    data = login.json()
    return data["access_token"], data["user"]["id"]


@pytest.mark.asyncio
async def test_content_download_endpoints():
    client = TestClient(app)

    owner_token, owner_id = _register_user(client, "event_organizer")
    other_token, _ = _register_user(client, "regular_user")

    # Create a content piece owned by owner
    create_res = client.post(
        "/api/v1/content",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Autonomous AI Agents in 2026",
            "body": "Key takeaway: AI agents are shifting from passive chat to active workflows.",
            "type": "summary",
        },
    )
    assert create_res.status_code == 201, create_res.text
    content_data = create_res.json()
    content_id = content_data["id"]

    # 1. Authenticated owner can download own content
    res_owner = client.get(
        f"/api/v1/content/{content_id}/download?format=markdown",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_owner.status_code == 200

    # 2. Unauthorized user cannot download another user's content (404 to avoid exposing existence)
    res_unauth = client.get(
        f"/api/v1/content/{content_id}/download?format=markdown",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res_unauth.status_code == 404

    # Unauthenticated request rejected (401 or 403)
    res_noauth = client.get(f"/api/v1/content/{content_id}/download?format=markdown")
    assert res_noauth.status_code in [401, 403]

    # 3. Markdown export returns correct response & MIME type
    res_md = client.get(
        f"/api/v1/content/{content_id}/download?format=markdown",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers.get("content-type", "")
    assert f'filename="EventAI_{content_id}.md"' in res_md.headers.get("content-disposition", "")
    md_text = res_md.text
    assert "# Autonomous AI Agents in 2026" in md_text
    assert "Key takeaway: AI agents are shifting from passive chat to active workflows." in md_text

    # 4. Text export returns correct response & MIME type
    res_txt = client.get(
        f"/api/v1/content/{content_id}/download?format=text",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_txt.status_code == 200
    assert "text/plain" in res_txt.headers.get("content-type", "")
    assert f'filename="EventAI_{content_id}.txt"' in res_txt.headers.get("content-disposition", "")
    txt_text = res_txt.text
    assert "Autonomous AI Agents in 2026" in txt_text
    assert "Key takeaway: AI agents are shifting from passive chat to active workflows." in txt_text

    # 5. JSON export returns correct response & MIME type
    res_json = client.get(
        f"/api/v1/content/{content_id}/download?format=json",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers.get("content-type", "")
    assert f'filename="EventAI_{content_id}.json"' in res_json.headers.get("content-disposition", "")
    json_data = res_json.json()
    assert json_data["id"] == content_id
    assert json_data["title"] == "Autonomous AI Agents in 2026"
    assert "Key takeaway: AI agents are shifting from passive chat to active workflows." in json_data["body"]
    assert json_data["status"] == "approved"

    # 6. Unsupported format is rejected with HTTP 400
    res_bad_format = client.get(
        f"/api/v1/content/{content_id}/download?format=pdf",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_bad_format.status_code == 400
    assert "Unsupported format" in res_bad_format.text


@pytest.mark.asyncio
async def test_event_transcript_access():
    client = TestClient(app)

    org_token, org_id = _register_user(client, "event_organizer")
    attendee_token, _ = _register_user(client, "regular_user")
    admin_token, _ = _register_user(client, "admin")

    # Create an event
    event_res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "name": "Pune Developer Summit 2026",
            "date": str(date.today()),
            "topic": "Scaling Generative AI Applications",
            "type": "event",
        },
    )
    assert event_res.status_code == 201, event_res.text
    event_id = event_res.json()["id"]

    # 10. Unknown event returns 404
    fake_event_id = str(uuid.uuid4())
    res_fake = client.get(
        f"/api/v1/events/{fake_event_id}/transcript",
        headers={"Authorization": f"Bearer {attendee_token}"},
    )
    assert res_fake.status_code == 404
    assert "Event not found" in res_fake.text

    # 11. Event with no completed transcript returns appropriate 404
    res_no_transcript = client.get(
        f"/api/v1/events/{event_id}/transcript",
        headers={"Authorization": f"Bearer {attendee_token}"},
    )
    assert res_no_transcript.status_code == 404
    assert "Transcript not found" in res_no_transcript.text

    # Seed Job and Transcript for this event (with ZERO ContentPieces)
    job_id = uuid.uuid4()
    transcript_id = uuid.uuid4()
    async with SessionLocal() as db:
        job = Job(
            id=job_id,
            user_id=uuid.UUID(org_id),
            event_id=uuid.UUID(event_id),
            status="completed",
        )
        db.add(job)
        transcript = Transcript(
            id=transcript_id,
            recording_id=uuid.uuid4(),
            job_id=job.id,
            full_text="Welcome to Pune Developer Summit 2026. This is the grounded conference transcript.",
            language="en",
            avg_confidence=0.91,
            quality_json={"duration_sec": 180.0, "ok": True},
            segments=[
                {
                    "start": 0.0,
                    "end": 12.0,
                    "text": "Welcome to Pune Developer Summit 2026.",
                    "speaker": "Keynote Speaker",
                    "confidence": 0.94,
                }
            ],
            provider="videodb",
        )
        db.add(transcript)
        await db.commit()

    # 7. Event owner can access event transcript
    res_org = client.get(
        f"/api/v1/events/{event_id}/transcript",
        headers={"Authorization": f"Bearer {org_token}"},
    )
    assert res_org.status_code == 200
    org_trans = res_org.json()
    assert "Pune Developer Summit 2026" in org_trans["full_text"]
    assert org_trans["job_id"] == str(job_id)
    assert org_trans["badge"] == "high"

    # 8. Regular authenticated attendee can access event transcript
    res_att = client.get(
        f"/api/v1/events/{event_id}/transcript",
        headers={"Authorization": f"Bearer {attendee_token}"},
    )
    assert res_att.status_code == 200
    att_trans = res_att.json()
    assert att_trans["full_text"] == org_trans["full_text"]
    assert att_trans["job_id"] == str(job_id)

    # 9. Admin can access event transcript
    res_adm = client.get(
        f"/api/v1/events/{event_id}/transcript",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_adm.status_code == 200
    adm_trans = res_adm.json()
    assert adm_trans["full_text"] == org_trans["full_text"]
    assert adm_trans["job_id"] == str(job_id)

    # 12. Transcript endpoint works even when event has zero ContentPiece/community posts
    # Verify no content pieces exist for this event
    content_list_res = client.get(
        f"/api/v1/content?event_id={event_id}",
        headers={"Authorization": f"Bearer {attendee_token}"},
    )
    assert content_list_res.status_code == 200
    assert content_list_res.json() == []
    # Transcript still returns 200 with full transcript data
    res_zero_posts = client.get(
        f"/api/v1/events/{event_id}/transcript",
        headers={"Authorization": f"Bearer {attendee_token}"},
    )
    assert res_zero_posts.status_code == 200
    assert res_zero_posts.json()["full_text"] == org_trans["full_text"]
