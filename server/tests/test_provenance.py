"""Claim-level provenance, coverage-balanced retrieval and the recording endpoint."""

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.graphs.agents.base import _retrieved_block
from app.main import app
from app.services.provenance import (
    build_windows,
    split_claims,
    temporal_spread,
    timed_words,
    trace_claims,
)
from app.services.rag import BAG_MODEL, bag_vector, rank_chunks

TALK = (
    "Good morning everyone. Today I want to talk about coral reefs and why they matter. "
    "Coral reefs cover less than one percent of the ocean floor but host a quarter of marine species. "
    "Then there is the problem of warming water, which causes coral bleaching across the Pacific. "
    "Bleaching happened on 70 percent of the Great Barrier Reef during the 2016 heatwave. "
    "Finally I want to share what gives me hope: restoration nurseries are regrowing coral fragments "
    "on underwater frames, and local fishing communities are protecting the reefs themselves."
)


def test_claims_skip_markdown_noise_and_short_lines() -> None:
    body = (
        "# Saving the Reefs\n\n"
        "**Coral reefs host a quarter of all marine species.**\n"
        "- Bleaching hit 70 percent of the Great Barrier Reef in 2016.\n"
        "| Col | Col |\n|---|---|\n"
        "Read more!\n#coral #ocean #climate"
    )
    claims = split_claims(body)
    assert claims == [
        "Coral reefs host a quarter of all marine species.",
        "Bleaching hit 70 percent of the Great Barrier Reef in 2016.",
    ]


def test_trace_claims_points_at_the_right_part_of_the_talk() -> None:
    body = (
        "Bleaching hit 70 percent of the Great Barrier Reef during the 2016 heatwave.\n"
        "Restoration nurseries regrow coral fragments on underwater frames.\n"
        "Quantum computers will replace every bank by next Tuesday afternoon."
    )
    result = trace_claims(body, TALK)
    statuses = [c["status"] for c in result["claims"]]
    assert statuses[:2] == ["traced", "traced"]
    assert statuses[2] == "untraced"
    assert result["claims"][2]["evidence"] is None
    first, second = result["claims"][0]["position"], result["claims"][1]["position"]
    assert first < second  # the bleaching point comes before the restoration point
    assert "70 percent" in result["claims"][0]["evidence"]
    assert result["summary"]["claims"] == 3
    assert result["summary"]["traced"] == 2


def test_timestamps_follow_segments_even_when_segment_text_is_shortened() -> None:
    words = TALK.split()
    half = len(words) // 2
    # Like Vertex STT: the stored segment text is only a preview of the chunk.
    segments = [
        {"text": " ".join(words[:8]), "start": 0.0, "end": 100.0},
        {"text": " ".join(words[half : half + 8]), "start": 100.0, "end": 300.0},
    ]
    timed = timed_words(TALK, segments)
    assert len(timed) == len(words)
    assert timed[0][1] == 0.0
    assert timed[half][1] == 100.0
    assert 100.0 < timed[-1][1] < 300.0
    windows = build_windows(TALK, segments)
    assert windows[0]["start"] == 0.0


def test_text_uploads_have_positions_but_no_times() -> None:
    result = trace_claims("Coral reefs host a quarter of marine species on the ocean floor.", TALK)
    claim = result["claims"][0]
    assert claim["status"] == "traced"
    assert claim["start"] is None
    assert claim["position"] is not None


def test_temporal_spread_counts_quarters() -> None:
    assert temporal_spread([0.1, 0.3, 0.6, 0.9]) == {"bins": [1, 1, 1, 1], "spread": 1.0}
    assert temporal_spread([0.8, 0.95, 1.0]) == {"bins": [0, 0, 0, 3], "spread": 0.25}
    assert temporal_spread([])["spread"] == 0.0


def _pool(items):
    return [
        {"text": t, "source": "this_event", "source_id": "j", "model": BAG_MODEL,
         "vector": bag_vector(t), "position": pos}
        for t, pos in items
    ]


def test_balanced_strategy_spreads_picks_over_the_talk() -> None:
    query = "kubernetes autoscaling in production"
    pool = _pool([
        ("kubernetes autoscaling in production at scale", 0.92),
        ("kubernetes autoscaling in production lessons", 0.95),
        ("kubernetes autoscaling production tuning", 0.97),
        ("we started with kubernetes on a small cluster", 0.35),
        ("the middle of the story was about kubernetes costs", 0.6),
    ])
    _, similar = asyncio.run(rank_chunks(pool, query, 3))
    _, balanced = asyncio.run(rank_chunks(pool, query, 3, "balanced"))
    assert min(c["position"] for c in similar) >= 0.9  # all from the end of the talk
    positions = [c["position"] for c in balanced]
    assert positions == sorted(positions)  # handed to the writers in talk order
    assert positions[0] < 0.5 and positions[-1] > 0.9


def test_balanced_prompt_labels_positions_and_asks_for_whole_talk() -> None:
    chunks = [{"text": "late point", "source": "this_event", "position": 0.62}]
    plain = _retrieved_block(chunks)
    balanced = _retrieved_block(chunks, balanced=True)
    assert "(this event, later in the recording) late point" in plain
    assert "beginning, the middle and the end" not in plain
    assert "(this event, ~62% into the recording) late point" in balanced
    assert "beginning, the middle and the end" in balanced


def _token(client: TestClient) -> str:
    email = f"prov_{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/v1/auth/register",
                      json={"email": email, "password": "password123", "role": "event_organizer"})
    return res.json()["access_token"]


def test_provenance_endpoint_and_media_for_a_text_upload() -> None:
    with TestClient(app) as client:
        token = _token(client)
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/api/v1/uploads", headers=headers,
            files={"file": ("talk.txt", TALK.encode(), "text/plain")},
            data={"consent_confirmed": "true", "requested_types": "summary", "target_languages": "en"},
        )
        assert upload.status_code == 202
        job_id = upload.json()["id"]
        pieces = client.get(f"/api/v1/jobs/{job_id}/content", headers=headers).json()
        assert pieces
        res = client.get(f"/api/v1/content/{pieces[0]['id']}/provenance", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["available"] is True
        assert body["method"] == "bm25-window"
        assert body["summary"]["claims"] == len(body["claims"])

        # Another user cannot read the provenance of an unapproved draft.
        other = {"Authorization": f"Bearer {_token(client)}"}
        assert client.get(f"/api/v1/content/{pieces[0]['id']}/provenance", headers=other).status_code == 404

        # A text upload has no recording to play.
        assert client.get(f"/api/v1/jobs/{job_id}/media?token={token}").status_code == 404


def test_media_endpoint_streams_and_seeks_the_recording(tmp_path) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.job import Job
    from app.models.recording import Recording

    audio = tmp_path / "talk.wav"
    audio.write_bytes(bytes(range(256)) * 40)

    with TestClient(app) as client:
        token = _token(client)
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/api/v1/uploads", headers=headers,
            files={"file": ("talk.txt", TALK.encode(), "text/plain")},
            data={"consent_confirmed": "true", "requested_types": "summary", "target_languages": "en"},
        )
        job_id = upload.json()["id"]

        async def point_at_audio() -> None:
            async with SessionLocal() as db:
                job = (await db.execute(select(Job).where(Job.id == uuid.UUID(job_id)))).scalar_one()
                rec = (await db.execute(select(Recording).where(Recording.id == job.recording_id))).scalar_one()
                rec.storage_uri, rec.content_type = str(audio), "audio/wav"
                await db.commit()

        client.portal.call(point_at_audio)

        full = client.get(f"/api/v1/jobs/{job_id}/media?token={token}")
        assert full.status_code == 200
        assert full.headers["content-type"] == "audio/wav"
        assert full.content == audio.read_bytes()

        # The audio player seeks with Range requests.
        part = client.get(f"/api/v1/jobs/{job_id}/media?token={token}", headers={"Range": "bytes=1000-1099"})
        assert part.status_code == 206
        assert part.content == audio.read_bytes()[1000:1100]

        # Only the owner can play it, and a bad token is rejected.
        assert client.get(f"/api/v1/jobs/{job_id}/media?token={_token(client)}").status_code == 404
        assert client.get(f"/api/v1/jobs/{job_id}/media?token=nope").status_code == 401
