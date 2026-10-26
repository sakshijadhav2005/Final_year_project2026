"""Regression tests for the defects found by the live evaluation (evaluation/paper, Sec. VI)."""

import asyncio
import types
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.providers.gemini_llm import _extract_json
from app.providers.stt import TranscriptResult
from app.services import credentials, degraded, transcription
from app.services.resilience import CircuitBreaker, CircuitOpenError, with_backoff

GOOD = '{"title": "ok", "body": "grounded"}'


# --- circuit breaker -------------------------------------------------------------------


def test_circuit_breaker_short_circuits_after_fail_max(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("app.services.resilience.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker("t", fail_max=3, reset_seconds=10)
    invoked = 0

    async def boom():
        nonlocal invoked
        invoked += 1
        raise RuntimeError("500 INTERNAL")

    async def run(n):
        blocked = 0
        for _ in range(n):
            try:
                await with_backoff(boom, circuit=breaker, attempts=1)
            except CircuitOpenError:
                blocked += 1
            except RuntimeError:
                pass
        return blocked

    assert asyncio.run(run(8)) == 5  # 3 real failures open the breaker, 5 calls rejected
    assert invoked == 3

    clock[0] += 11  # half-open: one trial call goes through again
    async def ok():
        return "fine"

    assert asyncio.run(with_backoff(ok, circuit=breaker, attempts=1)) == "fine"
    assert not breaker.is_open and breaker.failures == 0


# --- response shape --------------------------------------------------------------------


def test_extract_json_always_returns_an_object() -> None:
    assert _extract_json('[{"topics": ["a"], "brief": {"angle": "x"}}]') == {
        "topics": ["a"],
        "brief": {"angle": "x"},
    }
    assert _extract_json('[{"topics": ["a"]}, {"brief": {"angle": "x"}}]') == {
        "topics": ["a"],
        "brief": {"angle": "x"},
    }
    assert _extract_json('["just", "strings"]') == {"raw": '["just", "strings"]'}
    assert _extract_json("```json\n" + GOOD + "\n```") == {"title": "ok", "body": "grounded"}


def test_analysis_reasks_once_when_the_shape_is_wrong(monkeypatch) -> None:
    from app.graphs.nodes import analysis

    prompts: list[str] = []

    class Llm:
        async def generate_json(self, *, system, user, temperature=0.3, fast=False):
            prompts.append(user)
            if len(prompts) == 1:
                return {"raw": "[1, 2, 3]"}
            return {"topics": ["AI"], "brief": {"angle": "a", "key_messages": ["m"]}}

    monkeypatch.setattr(analysis, "get_llm_provider", lambda: Llm())
    out = asyncio.run(analysis.parallel_analysis({"transcript_text": "talk"}))
    assert len(prompts) == 2 and "not an array" in prompts[1]
    assert out["topics"] == {"topics": ["AI"]} and out["brief"]["angle"] == "a"


def test_analysis_never_crashes_on_a_wrong_shape(monkeypatch) -> None:
    from app.graphs.nodes import analysis

    class Llm:
        async def generate_json(self, **_):
            return {"raw": "still wrong"}

    monkeypatch.setattr(analysis, "get_llm_provider", lambda: Llm())
    out = asyncio.run(analysis.parallel_analysis({"transcript_text": "talk"}))
    assert set(out) == {"topics", "highlights", "speakers", "sentiment"}


# --- Vertex model selection ------------------------------------------------------------


class _FakeVertex:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls: list[str] = []
        self.aio = self
        self.models = self

    async def generate_content(self, *, model, contents, config=None):
        self.calls.append(model)
        return types.SimpleNamespace(text=self.behaviour(model, self.calls.count(model)))


@pytest.fixture
def vertex(monkeypatch):
    from app.providers import vertex_llm

    s = get_settings()
    monkeypatch.setattr(s, "google_cloud_project", "test-project")
    monkeypatch.setattr(s, "google_cloud_location", "global")
    monkeypatch.setattr(s, "vertex_model", "")
    monkeypatch.setattr(s, "gemini_model_generate", "gemini-3.1-flash-lite")
    monkeypatch.setattr(vertex_llm, "_DEAD_MODELS", set())
    monkeypatch.setattr(vertex_llm, "_CLIENTS", {})

    def install(behaviour):
        fake = _FakeVertex(behaviour)
        vertex_llm._CLIENTS[("test-project", "global")] = fake
        return fake

    return install


def test_one_empty_reply_does_not_switch_the_model_for_good(vertex) -> None:
    from app.providers.vertex_llm import VertexLLMProvider

    fake = vertex(lambda m, n: "" if (m == "gemini-3.1-flash-lite" and n == 1) else GOOD)
    p = VertexLLMProvider()
    assert asyncio.run(p.generate_json(system="s", user="u"))["title"] == "ok"
    assert fake.calls == ["gemini-3.1-flash-lite", "gemini-3.6-flash"]
    asyncio.run(p.generate_json(system="s", user="u"))
    assert fake.calls[-1] == "gemini-3.1-flash-lite"  # the configured model again


def test_a_failing_model_is_skipped_while_its_circuit_is_open(vertex) -> None:
    from app.providers.vertex_llm import VertexLLMProvider

    fake = vertex(lambda m, n: "" if m == "gemini-3.1-flash-lite" else GOOD)
    p = VertexLLMProvider()
    for _ in range(get_settings().model_circuit_fail_max):
        asyncio.run(p.generate_json(system="s", user="u"))
    before = fake.calls.count("gemini-3.1-flash-lite")
    asyncio.run(p.generate_json(system="s", user="u"))
    assert fake.calls.count("gemini-3.1-flash-lite") == before  # skipped, not retried
    assert fake.calls[-1] == "gemini-3.6-flash"


def test_offline_fallback_is_recorded_as_degraded(vertex) -> None:
    from app.providers.vertex_llm import VertexLLMProvider

    def fail(m, n):
        raise RuntimeError("500 INTERNAL")

    vertex(fail)
    events = degraded.start()
    out = asyncio.run(VertexLLMProvider().generate_json(system="s", user="TASK=blog\nx"))
    assert out  # the job still gets text
    assert events == ["llm_offline_template"]


def test_degraded_job_goes_to_human_review(monkeypatch) -> None:
    from app.providers.fake_llm import FakeLLMProvider

    original = FakeLLMProvider.generate_json

    async def flaky(self, **kwargs):
        degraded.mark("llm_offline_template")
        return await original(self, **kwargs)

    monkeypatch.setattr(FakeLLMProvider, "generate_json", flaky)
    with TestClient(app) as client:
        email = f"deg_{uuid.uuid4().hex[:8]}@example.com"
        res = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "role": "event_organizer"},
        )
        headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        res = client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": ("talk.txt", b"Speaker 1: a short talk about grounded content.", "text/plain")},
            data={"consent_confirmed": "true", "requested_types": "summary", "target_languages": "en"},
        )
        assert res.status_code == 202, res.text
        job = client.get(f"/api/v1/jobs/{res.json()['id']}", headers=headers).json()
    assert job["status"] == "needs_review"
    assert job["error_code"] == "degraded_output"


# --- credentials and speech-to-text fallback -------------------------------------------


def test_rejected_gemini_key_is_skipped(monkeypatch) -> None:
    from app.providers.factory import get_stt_provider

    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "bad-key")
    monkeypatch.setattr(s, "stt_provider", "auto")

    async def invalid(_key):
        return "invalid"

    monkeypatch.setattr(credentials, "_check_gemini", invalid)
    assert asyncio.run(credentials.validate_credentials())["gemini"] == "invalid"
    assert get_stt_provider().name == "fake"
    assert transcription._fallback_provider({"vertex-stt"}) is None


def test_stt_tries_every_remaining_engine(monkeypatch, tmp_path) -> None:
    audio = tmp_path / "talk.wav"
    audio.write_bytes(b"0" * 10)

    class Engine:
        def __init__(self, name, ok):
            self.name, self.ok = name, ok

        async def transcribe(self, path):
            if not self.ok:
                raise RuntimeError(f"{self.name} down")
            return TranscriptResult(
                text="hello", language="en", avg_confidence=0.95, provider=self.name,
                vendor_id="x", segments=[],
            )

    chain = [Engine("gemini-stt", False), Engine("videodb", True)]
    monkeypatch.setattr(transcription, "is_mostly_silent", lambda _p: False)
    monkeypatch.setattr(transcription, "get_stt_provider", lambda: Engine("vertex-stt", False))
    monkeypatch.setattr(
        transcription,
        "_fallback_provider",
        lambda tried: next((e for e in chain if e.name not in tried), None),
    )
    result = asyncio.run(transcription.transcribe_file(str(audio)))
    assert result.provider == "videodb"
