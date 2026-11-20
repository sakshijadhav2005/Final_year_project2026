"""Back-translation check on translated drafts (plan §13, limitation #7)."""

import asyncio
import uuid

from app.graphs.nodes import translator
from app.graphs.nodes.translator import back_translation_score
from app.main import app
from app.providers import fake_llm
from fastapi.testclient import TestClient

SAMPLE = (
    b"Speaker 1: Welcome to the EventAI meetup on intelligent content operations. "
    b"Today we discuss multi-agent pipelines, guardrails and human review."
)


def _headers(client: TestClient) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"bt_{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "role": "event_organizer",
        },
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_score_is_high_for_same_meaning_and_low_for_drift() -> None:
    original = "The keynote covered guardrails for multi-agent content pipelines."
    assert back_translation_score(original, original) == 1.0
    close = "The keynote discussed guardrails for multi-agent content pipelines."
    assert back_translation_score(original, close) > 0.7
    drift = "Tickets for the summer concert are on sale now."
    assert back_translation_score(original, drift) < 0.2
    assert back_translation_score(original, "") == 0.0


def _translate(monkeypatch, back_body: str | None):
    orig = fake_llm.FakeLLMProvider.generate_json

    async def fake(self, *, system, user, temperature=0.3, **kw):
        if "TASK=translation_batch" in user:
            return {"drafts": {"blog": {"title": "Titel", "body": "Übersetzter Text"}}}
        if "TASK=back_translation_batch" in user:
            if back_body is None:
                raise RuntimeError("model down")
            return {"drafts": {"blog": {"title": "Guardrails", "body": back_body}}}
        return await orig(self, system=system, user=user, temperature=temperature)

    monkeypatch.setattr(fake_llm.FakeLLMProvider, "generate_json", fake)
    state = {
        "target_languages": ["en", "de"],
        "generated": [
            {
                "type": "blog",
                "title": "Guardrails",
                "body": "Guardrails keep multi-agent content pipelines honest and reviewable.",
            }
        ],
    }
    out = asyncio.run(translator.translation(state))
    (item,) = out["translations"]
    return item


def test_faithful_translation_passes(monkeypatch) -> None:
    item = _translate(
        monkeypatch, "Guardrails keep multi-agent content pipelines honest and reviewable."
    )
    assert item["language"] == "de"
    assert item["back_translation"]["pass"] is True
    assert item["back_translation"]["status"] == "pass"


def test_drifted_translation_is_flagged(monkeypatch) -> None:
    item = _translate(monkeypatch, "The weather in Berlin was sunny on Tuesday afternoon.")
    check = item["back_translation"]
    assert check["pass"] is False
    assert check["status"] == "low_agreement"
    assert check["score"] < check["min_score"]
    assert "Berlin" in check["back_text"]


def test_failed_back_translation_is_unchecked_not_failed(monkeypatch) -> None:
    item = _translate(monkeypatch, None)
    assert item["back_translation"]["status"] == "unchecked"
    assert item["back_translation"]["pass"] is None
    assert item["body"] == "Übersetzter Text"  # the translation itself is kept


def test_verdict_is_saved_on_translated_pieces_only() -> None:
    with TestClient(app) as client:
        headers = _headers(client)
        res = client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("session.txt", SAMPLE, "text/plain")},
            data={"consent_confirmed": "true", "requested_types": "summary", "target_languages": "en,hi"},
        )
        assert res.status_code == 202, res.text
        content = client.get(f"/api/v1/jobs/{res.json()['id']}/content", headers=headers).json()
        hindi = [c for c in content if c["language"] == "hi"]
        english = [c for c in content if c["language"] == "en"]
        assert hindi and english
        assert hindi[0]["grounding"]["back_translation"]["status"] in {"pass", "low_agreement", "unchecked"}
        assert "back_translation" not in (english[0]["grounding"] or {})
