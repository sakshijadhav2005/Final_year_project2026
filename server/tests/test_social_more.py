"""Scheduling, Facebook Pages, X, and draft-kind detection. All platforms are mocked."""

import asyncio
import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from app.core.config import get_settings
from app.main import app
from app.services import publishers, social_publishing
from app.services.publishers import x
from fastapi.testclient import TestClient


class FakePlatforms:
    """LinkedIn, Facebook and X endpoints in one mock transport."""

    def __init__(self) -> None:
        self.linkedin_posts: list[dict] = []
        self.facebook_posts: list[dict] = []
        self.x_posts: list[dict] = []
        self.x_verifier_seen: str | None = None
        self.x_refreshes = 0
        self.x_expires_in = 7200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        # LinkedIn
        if path == "/oauth/v2/accessToken":
            return httpx.Response(200, json={"access_token": "li", "expires_in": 5184000})
        if path == "/v2/userinfo":
            return httpx.Response(200, json={"sub": "m1", "name": "Asha"})
        if path == "/rest/posts":
            self.linkedin_posts.append(json.loads(request.content))
            return httpx.Response(201, headers={"x-restli-id": f"urn:li:share:{len(self.linkedin_posts)}"})
        # Facebook
        if host == "graph.facebook.com" and path.endswith("/oauth/access_token"):
            params = request.url.params
            if params.get("grant_type") == "fb_exchange_token":
                assert params["fb_exchange_token"] == "fb-short"
                return httpx.Response(200, json={"access_token": "fb-long", "expires_in": 5184000})
            return httpx.Response(200, json={"access_token": "fb-short"})
        if host == "graph.facebook.com" and path.endswith("/me/accounts"):
            assert request.url.params["access_token"] == "fb-long"
            return httpx.Response(200, json={"data": [{"id": "555", "name": "Pune AI Meetup", "access_token": "page-tok"}]})
        if host == "graph.facebook.com" and path.endswith("/555/feed"):
            form = parse_qs(request.content.decode())
            assert form["access_token"] == ["page-tok"]
            self.facebook_posts.append({"message": form["message"][0]})
            return httpx.Response(200, json={"id": "555_777"})
        # X
        if host == "api.x.com" and path == "/2/oauth2/token":
            form = parse_qs(request.content.decode())
            assert request.headers["Authorization"].startswith("Basic ")
            if form["grant_type"] == ["refresh_token"]:
                self.x_refreshes += 1
                return httpx.Response(200, json={"access_token": "x-new", "refresh_token": "x-r2", "expires_in": 7200})
            self.x_verifier_seen = form["code_verifier"][0]
            return httpx.Response(
                200, json={"access_token": "x-tok", "refresh_token": "x-r1", "expires_in": self.x_expires_in}
            )
        if host == "api.x.com" and path == "/2/users/me":
            return httpx.Response(200, json={"data": {"id": "99", "name": "Asha", "username": "asha_ai"}})
        if host == "api.x.com" and path == "/2/tweets":
            self.x_posts.append({"auth": request.headers["Authorization"], **json.loads(request.content)})
            return httpx.Response(201, json={"data": {"id": "1234", "text": "ok"}})
        return httpx.Response(404)


@pytest.fixture
def fake(monkeypatch):
    s = get_settings()
    for key, value in {
        "linkedin_client_id": "li-id", "linkedin_client_secret": "li-secret",
        "facebook_app_id": "fb-id", "facebook_app_secret": "fb-secret",
        "x_client_id": "x-id", "x_client_secret": "x-secret",
    }.items():
        monkeypatch.setattr(s, key, value)
    f = FakePlatforms()
    monkeypatch.setattr(publishers, "HTTP_TRANSPORT", httpx.MockTransport(f))
    return f


def _user(client: TestClient) -> dict:
    email = f"more_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "role": "event_organizer"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _connect(client: TestClient, headers: dict, platform: str) -> tuple[httpx.Response, dict]:
    r = client.get(f"/api/v1/social/{platform}/connect", headers=headers)
    assert r.status_code == 200, r.text
    query = parse_qs(urlparse(r.json()["authorize_url"]).query)
    cb = client.get(
        f"/api/v1/social/{platform}/callback",
        params={"code": "c", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert cb.headers["location"].endswith("status=connected"), cb.headers["location"]
    return cb, query


def _draft(client: TestClient, headers: dict, type_: str, body: str) -> str:
    r = client.post("/api/v1/content", headers=headers, json={"title": "Recap", "body": body, "type": type_})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── draft kinds ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("content_type", "kind"),
    [("linkedin", "linkedin"), ("linkedin_post", "linkedin"), ("ig_caption", "instagram"),
     ("instagram", "instagram"), ("x_post", "x"), ("tweet", "x"), ("flyer", None), ("blog", None)],
)
def test_kind_for_type(content_type, kind) -> None:
    assert social_publishing.kind_for_type(content_type) == kind


# ── Facebook ───────────────────────────────────────────────────────────────────


def test_facebook_posts_to_first_page_with_page_token(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "facebook")
        accounts = {a["platform"]: a for a in client.get("/api/v1/social/accounts", headers=headers).json()}
        assert accounts["facebook"]["account"]["display_name"] == "Pune AI Meetup"

        content_id = _draft(client, headers, "ig_caption", "Thanks all! #AI")
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "facebook"})
        assert r.status_code == 200, r.text
        assert r.json()["post_url"] == "https://www.facebook.com/555_777"
        assert fake.facebook_posts == [{"message": "Thanks all! #AI"}]


def test_platform_rejects_the_wrong_draft_kind(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "x")
        content_id = _draft(client, headers, "linkedin_post", "A long LinkedIn post")
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "x"})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "wrong_type"


# ── X ──────────────────────────────────────────────────────────────────────────


def test_x_uses_pkce_and_posts(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _, query = _connect(client, headers, "x")
        assert query["code_challenge_method"] == ["S256"]
        expected = base64.urlsafe_b64encode(hashlib.sha256(fake.x_verifier_seen.encode()).digest()).rstrip(b"=").decode()
        assert query["code_challenge"] == [expected]  # the verifier came from our cookie

        content_id = _draft(client, headers, "x_post", "Shipping agents to prod? Three lessons from #PuneAI 🧵")
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "x"})
        assert r.status_code == 200, r.text
        assert r.json()["post_url"] == "https://x.com/i/web/status/1234"
        assert fake.x_posts[0]["text"].endswith("#PuneAI 🧵")
        assert fake.x_posts[0]["auth"] == "Bearer x-tok"


def test_x_refreshes_an_expired_token(fake) -> None:
    fake.x_expires_in = -10  # the token is already expired when stored
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "x")
        content_id = _draft(client, headers, "x_post", "short post")
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "x"})
        assert r.status_code == 200, r.text
        assert fake.x_refreshes == 1
        assert fake.x_posts[0]["auth"] == "Bearer x-new"


def test_x_weighted_length() -> None:
    assert x.weighted_length("hello") == 5
    assert x.weighted_length("see https://example.com/a/very/long/path?x=1 ok") == 4 + 23 + 3
    assert x.weighted_length("日本") == 4  # CJK counts double
    with pytest.raises(publishers.PublishError):
        x.check_text("a" * 281)
    x.check_text("a" * 280)


# ── Scheduling ─────────────────────────────────────────────────────────────────


def _future(minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def test_schedule_then_send_when_due(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "linkedin")
        content_id = _draft(client, headers, "linkedin_post", "Scheduled hello #AI")

        r = client.post(
            f"/api/v1/content/{content_id}/publish",
            headers=headers,
            json={"platform": "linkedin", "scheduled_for": _future(30)},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "scheduled"
        assert fake.linkedin_posts == []

        again = client.post(
            f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "linkedin"}
        )
        assert again.status_code == 409  # already scheduled

        # Not due yet: nothing is sent.
        assert asyncio.run(social_publishing.run_due_posts()) == 0
        # Half an hour later it goes out, exactly once.
        later = datetime.now(UTC) + timedelta(minutes=31)
        assert asyncio.run(social_publishing.run_due_posts(now=later)) == 1
        assert asyncio.run(social_publishing.run_due_posts(now=later)) == 0
        assert len(fake.linkedin_posts) == 1

        history = client.get(f"/api/v1/content/{content_id}/publications", headers=headers).json()
        assert history[0]["status"] == "posted"


def test_cancel_scheduled_post(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "linkedin")
        content_id = _draft(client, headers, "linkedin_post", "Maybe later")
        post = client.post(
            f"/api/v1/content/{content_id}/publish",
            headers=headers,
            json={"platform": "linkedin", "scheduled_for": _future(10)},
        ).json()

        stranger = _user(client)
        assert client.delete(f"/api/v1/social/posts/{post['id']}", headers=stranger).status_code == 404

        r = client.delete(f"/api/v1/social/posts/{post['id']}", headers=headers)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        assert client.delete(f"/api/v1/social/posts/{post['id']}", headers=headers).status_code == 409

        asyncio.run(social_publishing.run_due_posts(now=datetime.now(UTC) + timedelta(hours=1)))
        assert fake.linkedin_posts == []
        # After cancelling it can be published again.
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "linkedin"})
        assert r.status_code == 200


def test_schedule_time_must_be_in_the_future(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "linkedin")
        content_id = _draft(client, headers, "linkedin_post", "x")
        for when in (_future(-5), _future(60 * 24 * 61)):
            r = client.post(
                f"/api/v1/content/{content_id}/publish",
                headers=headers,
                json={"platform": "linkedin", "scheduled_for": when},
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "invalid_schedule"


def test_scheduled_post_fails_if_draft_was_rejected(fake) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers, "linkedin")
        content_id = _draft(client, headers, "linkedin_post", "Will be pulled")
        client.post(
            f"/api/v1/content/{content_id}/publish",
            headers=headers,
            json={"platform": "linkedin", "scheduled_for": _future(5)},
        )
        client.post(f"/api/v1/content/{content_id}/reject", headers=headers, json={"reason": "typo"})
        asyncio.run(social_publishing.run_due_posts(now=datetime.now(UTC) + timedelta(minutes=10)))
        assert fake.linkedin_posts == []
        history = client.get(f"/api/v1/content/{content_id}/publications", headers=headers).json()
        assert history[0]["status"] == "failed"
        assert "no longer approved" in history[0]["error"]


# ── X drafts from the pipeline ─────────────────────────────────────────────────


def test_pipeline_writes_an_x_post_within_the_limit() -> None:
    from app.graphs.pipeline import get_compiled_graph

    transcript = (
        "Speaker 1: Welcome to the meetup on multi agent pipelines and guardrails. "
        "Running extraction agents in parallel cut our latency from eighteen seconds to three. " * 8
    )
    state = {
        "job_id": "t", "user_id": "u", "transcript_text": transcript, "avg_confidence": 0.99,
        "quality": {"ok": True}, "requested_types": ["x_post"], "target_languages": ["en"],
        "use_org_memory": False, "user_memory": {}, "retry_count": 0, "rag_chunks": [],
    }
    final = asyncio.run(get_compiled_graph().ainvoke(state))
    drafts = [p for p in final["generated"] if p["type"] == "x_post"]
    assert len(drafts) == 1
    assert 0 < x.weighted_length(drafts[0]["body"]) <= 280


def test_fit_x_limit_cuts_on_a_word() -> None:
    from app.graphs.agents.x_agent import fit_x_limit

    text = fit_x_limit("**Bold** " + "word " * 100)
    assert x.weighted_length(text) <= 280
    assert text.endswith("word…") and "**" not in text


# ── Chat co-pilot sees publishing status ───────────────────────────────────────


def test_copilot_prompt_includes_publishing_status(fake, monkeypatch) -> None:
    from app.services import chat_service

    seen: dict = {}
    original = chat_service._build_chat_system_prompt

    def capture(persona, transcript_text=None, publishing=None):
        seen["persona"], seen["publishing"] = persona, publishing
        return original(persona, transcript_text, publishing)

    monkeypatch.setattr(chat_service, "_build_chat_system_prompt", capture)
    with TestClient(app) as client:
        headers = _user(client)
        event = client.post(
            "/api/v1/events", headers=headers, json={"name": "Pune AI", "date": "2026-11-20", "type": "meetup"}
        )
        assert event.status_code == 201, event.text
        event_id = event.json()["id"]
        _connect(client, headers, "linkedin")
        r = client.post(
            "/api/v1/content",
            headers=headers,
            json={"title": "Recap", "body": "Live now #AI", "type": "linkedin_post", "event_id": event_id},
        )
        client.post(f"/api/v1/content/{r.json()['id']}/publish", headers=headers, json={"platform": "linkedin"})

        res = client.post(
            "/api/v1/chat/stream",
            headers=headers,
            json={"message": "What is posted?", "event_id": event_id, "persona": "organizer_copilot"},
        )
        assert res.status_code == 200
        _ = res.text  # drain the stream
    assert seen["persona"] == "organizer_copilot"
    [draft] = seen["publishing"]
    assert draft["platforms"]["linkedin"]["status"] == "posted"
    assert draft["platforms"]["linkedin"]["post_url"].startswith("https://www.linkedin.com/")
    prompt = original("organizer_copilot", None, seen["publishing"])
    assert "SOCIAL PUBLISHING STATUS" in prompt and "cannot publish" in prompt
