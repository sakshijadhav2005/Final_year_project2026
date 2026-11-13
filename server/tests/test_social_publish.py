"""Connect LinkedIn and publish approved drafts. LinkedIn is mocked; nothing leaves the machine."""

import asyncio
import json
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from app.core.config import get_settings
from app.main import app
from app.services import publishers
from app.services.publishers import linkedin
from fastapi.testclient import TestClient
from sqlalchemy import select, update


class FakeLinkedIn:
    """Answers the three LinkedIn endpoints EventAI calls and records what it was sent."""

    def __init__(self) -> None:
        self.posts: list[dict] = []
        self.post_status = 201

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/accessToken":
            form = parse_qs(request.content.decode())
            assert form["grant_type"] == ["authorization_code"]
            assert form["code"] == ["good-code"]
            return httpx.Response(
                200, json={"access_token": "li-token-123", "expires_in": 5184000, "scope": linkedin.SCOPES}
            )
        if request.url.path == "/v2/userinfo":
            assert request.headers["Authorization"] == "Bearer li-token-123"
            return httpx.Response(200, json={"sub": "member42", "name": "Asha Rao"})
        if request.url.path == "/rest/posts":
            assert request.headers["LinkedIn-Version"]
            assert request.headers["X-Restli-Protocol-Version"] == "2.0.0"
            if self.post_status != 201:
                return httpx.Response(self.post_status, json={"message": "nope"})
            self.posts.append(json.loads(request.content))
            return httpx.Response(201, headers={"x-restli-id": f"urn:li:share:{len(self.posts)}"})
        return httpx.Response(404)


@pytest.fixture
def fake_linkedin(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "linkedin_client_id", "client-abc")
    monkeypatch.setattr(settings, "linkedin_client_secret", "secret-xyz")
    fake = FakeLinkedIn()
    monkeypatch.setattr(publishers, "HTTP_TRANSPORT", httpx.MockTransport(fake))
    return fake


def _user(client: TestClient) -> dict:
    email = f"social_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "role": "event_organizer"}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _post(client: TestClient, headers: dict, body: str = "Great talk on #AI agents today!") -> str:
    r = client.post(
        "/api/v1/content", headers=headers, json={"title": "Recap", "body": body, "type": "linkedin_post"}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _connect(client: TestClient, headers: dict) -> httpx.Response:
    r = client.get("/api/v1/social/linkedin/connect", headers=headers)
    assert r.status_code == 200, r.text
    state = parse_qs(urlparse(r.json()["authorize_url"]).query)["state"][0]
    return client.get(
        "/api/v1/social/linkedin/callback",
        params={"code": "good-code", "state": state},
        follow_redirects=False,
    )


def _set_status(content_id: str, status: str) -> None:
    from app.db.session import SessionLocal
    from app.models.content import ContentPiece

    async def go():
        async with SessionLocal() as db:
            await db.execute(
                update(ContentPiece).where(ContentPiece.id == uuid.UUID(content_id)).values(status=status)
            )
            await db.commit()

    asyncio.run(go())


def test_connect_needs_server_credentials(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "linkedin_client_id", "")
    with TestClient(app) as client:
        headers = _user(client)
        r = client.get("/api/v1/social/linkedin/connect", headers=headers)
        assert r.status_code == 503
        accounts = client.get("/api/v1/social/accounts", headers=headers).json()
        assert accounts == [{"platform": "linkedin", "configured": False, "account": None}]


def test_connect_stores_encrypted_token(fake_linkedin) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        r = client.get("/api/v1/social/linkedin/connect", headers=headers)
        query = parse_qs(urlparse(r.json()["authorize_url"]).query)
        assert query["client_id"] == ["client-abc"]
        assert "w_member_social" in query["scope"][0]

        cb = _connect(client, headers)
        assert cb.status_code == 302
        assert cb.headers["location"].endswith("/settings?social=linkedin&status=connected")

        accounts = client.get("/api/v1/social/accounts", headers=headers).json()
        assert accounts[0]["configured"] is True
        assert accounts[0]["account"]["display_name"] == "Asha Rao"
        assert accounts[0]["account"]["expired"] is False

    from app.db.session import SessionLocal
    from app.models.social import SocialAccount

    async def stored():
        async with SessionLocal() as db:
            rows = (
                await db.execute(select(SocialAccount).where(SocialAccount.external_id == "member42"))
            ).scalars().all()
            return [r.access_token_enc for r in rows]

    tokens = asyncio.run(stored())
    assert tokens and all("li-token-123" not in t for t in tokens)


def test_callback_rejects_state_without_matching_cookie(fake_linkedin) -> None:
    """A sign-in link made for someone else's account must not attach to this browser."""
    with TestClient(app) as client:
        headers = _user(client)
        r = client.get("/api/v1/social/linkedin/connect", headers=headers)
        state = parse_qs(urlparse(r.json()["authorize_url"]).query)["state"][0]
    with TestClient(app) as other_browser:
        cb = other_browser.get(
            "/api/v1/social/linkedin/callback",
            params={"code": "good-code", "state": state},
            follow_redirects=False,
        )
        assert cb.status_code == 302
        assert "status=error" in cb.headers["location"]
        assert "reason=invalid_state" in cb.headers["location"]


def test_callback_reports_cancel(fake_linkedin) -> None:
    with TestClient(app) as client:
        cb = client.get(
            "/api/v1/social/linkedin/callback",
            params={"error": "user_cancelled_login"},
            follow_redirects=False,
        )
        assert "status=error" in cb.headers["location"]


def test_publish_approved_post(fake_linkedin) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers, "**Big news** from the meetup (Pune)!\n\n#AI #PuneDevs")

        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "linkedin"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "posted"
        assert r.json()["post_url"] == "https://www.linkedin.com/feed/update/urn:li:share:1/"

        sent = fake_linkedin.posts[0]
        assert sent["author"] == "urn:li:person:member42"
        assert sent["commentary"].startswith("Recap\n\nBig news from the meetup \\(Pune\\)!")
        assert "{hashtag|\\#|AI} {hashtag|\\#|PuneDevs}" in sent["commentary"]

        again = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={})
        assert again.status_code == 409
        assert len(fake_linkedin.posts) == 1

        history = client.get(f"/api/v1/content/{content_id}/publications", headers=headers).json()
        assert [h["status"] for h in history] == ["posted"]


def test_publish_requires_approval(fake_linkedin) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)
        _set_status(content_id, "pending_review")
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={})
        assert r.status_code == 409
        assert fake_linkedin.posts == []


def test_publish_requires_connection_and_ownership(fake_linkedin) -> None:
    with TestClient(app) as client:
        owner = _user(client)
        content_id = _post(client, owner)
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=owner, json={})
        assert r.status_code == 400  # not connected yet

        stranger = _user(client)
        _connect(client, stranger)
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=stranger, json={})
        assert r.status_code == 404
        assert fake_linkedin.posts == []


def test_expired_linkedin_token_asks_to_reconnect(fake_linkedin) -> None:
    fake_linkedin.post_status = 401
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "reconnect_required"
        history = client.get(f"/api/v1/content/{content_id}/publications", headers=headers).json()
        assert history[0]["status"] == "failed"


def test_disconnect(fake_linkedin) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        assert client.delete("/api/v1/social/accounts/linkedin", headers=headers).status_code == 204
        accounts = client.get("/api/v1/social/accounts", headers=headers).json()
        assert accounts[0]["account"] is None


def test_post_text_formatting() -> None:
    text = linkedin.build_post_text("Recap", "## Recap\n\n- one\n- **two**\n\nSee [docs](https://x.io) #AI_2026")
    assert text == "Recap\n\n• one\n• two\n\nSee docs (https://x.io) #AI_2026"
    commentary = linkedin.to_commentary(text)
    assert "{hashtag|\\#|AI_2026}" in commentary
    assert "\\(https://x.io\\)" in commentary
    assert linkedin.to_commentary("email me @ home, 50% off <now>") == "email me \\@ home, 50% off \\<now\\>"


def test_too_long_post_is_refused_before_calling_linkedin(fake_linkedin) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers, "word " * 700)
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "too_long"
        assert fake_linkedin.posts == []
