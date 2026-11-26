"""Instagram publishing: OAuth, recap card, uploads, two-step publish. Instagram is mocked."""

import io
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from app.core.config import get_settings
from app.main import app
from app.services import publishers
from app.services.publishers import images, instagram
from fastapi.testclient import TestClient
from PIL import Image

IG_USER = "17841400000000001"


class FakeInstagram:
    """Answers the Instagram endpoints EventAI calls. Downloads the post image through the
    public signed link, the way Instagram's servers would."""

    def __init__(self) -> None:
        self.containers: list[dict] = []
        self.published: list[str] = []
        self.downloaded: list[bytes] = []
        self.container_status = "FINISHED"
        self.publish_error: dict | None = None

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.host == "api.instagram.com" and path == "/oauth/access_token":
            form = parse_qs(request.content.decode())
            assert form["code"] == ["good-code"]  # the "#_" suffix is stripped
            return httpx.Response(
                200, json={"data": [{"access_token": "short", "user_id": "1", "permissions": "x"}]}
            )
        if path == "/access_token":
            assert request.url.params["access_token"] == "short"
            return httpx.Response(200, json={"access_token": "ig-long", "expires_in": 5184000})
        if path.endswith("/me"):
            return httpx.Response(200, json={"user_id": IG_USER, "username": "eventai_demo"})
        if path.endswith(f"/{IG_USER}/media"):
            form = parse_qs(request.content.decode())
            url = form["image_url"][0]
            assert url.startswith("http://public.test/api/v1/social/media/")
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://public.test"
            ) as downloader:
                res = await downloader.get(url)
            assert res.status_code == 200, res.text
            assert res.headers["content-type"] == "image/jpeg"
            self.downloaded.append(res.content)
            self.containers.append({"caption": form["caption"][0], "image_url": url})
            return httpx.Response(200, json={"id": "c1"})
        if path.endswith("/c1"):
            return httpx.Response(200, json={"status_code": self.container_status})
        if path.endswith("/media_publish"):
            if self.publish_error:
                return httpx.Response(400, json={"error": self.publish_error})
            self.published.append(parse_qs(request.content.decode())["creation_id"][0])
            return httpx.Response(200, json={"id": "m99"})
        if path.endswith("/m99"):
            return httpx.Response(200, json={"permalink": "https://www.instagram.com/p/ABC123/"})
        return httpx.Response(404)


@pytest.fixture
def fake_ig(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "instagram_client_id", "ig-app")
    monkeypatch.setattr(settings, "instagram_client_secret", "ig-secret")
    monkeypatch.setattr(settings, "public_base_url", "http://public.test")
    monkeypatch.setattr(instagram, "CONTAINER_POLL_SECONDS", 0)
    fake = FakeInstagram()
    monkeypatch.setattr(publishers, "HTTP_TRANSPORT", httpx.MockTransport(fake))
    return fake


def _user(client: TestClient) -> dict:
    email = f"ig_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "role": "event_organizer"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _connect(client: TestClient, headers: dict) -> httpx.Response:
    r = client.get("/api/v1/social/instagram/connect", headers=headers)
    assert r.status_code == 200, r.text
    query = parse_qs(urlparse(r.json()["authorize_url"]).query)
    assert query["scope"] == [instagram.SCOPES]
    return client.get(
        "/api/v1/social/instagram/callback",
        params={"code": "good-code#_", "state": query["state"][0]},
        follow_redirects=False,
    )


def _post(client: TestClient, headers: dict, body: str = "**Thanks** for coming! \U0001f389 #PuneDevs @friend") -> str:
    r = client.post(
        "/api/v1/content",
        headers=headers,
        json={"title": "Meetup recap", "body": body, "type": "instagram_caption"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_connect_instagram(fake_ig) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        cb = _connect(client, headers)
        assert cb.headers["location"].endswith("/settings?social=instagram&status=connected")
        accounts = {a["platform"]: a for a in client.get("/api/v1/social/accounts", headers=headers).json()}
        assert accounts["instagram"]["account"]["display_name"] == "@eventai_demo"
        assert accounts["linkedin"]["account"] is None


def test_publish_with_rendered_card(fake_ig) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)

        preview = client.get(f"/api/v1/content/{content_id}/social-image", headers=headers)
        assert preview.status_code == 200
        assert Image.open(io.BytesIO(preview.content)).size == images.CARD_SIZE

        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "instagram"})
        assert r.status_code == 200, r.text
        assert r.json()["post_url"] == "https://www.instagram.com/p/ABC123/"
        assert fake_ig.published == ["c1"]
        assert fake_ig.containers[0]["caption"] == "Thanks for coming! \U0001f389 #PuneDevs @friend"
        img = Image.open(io.BytesIO(fake_ig.downloaded[0]))
        assert img.format == "JPEG" and img.size == images.CARD_SIZE

        again = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "instagram"})
        assert again.status_code == 409


def test_publish_with_uploaded_image_is_padded_to_allowed_ratio(fake_ig) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (400, 1200), (10, 200, 10)).save(buf, format="PNG")  # 1:3, too tall
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)
        r = client.post(
            f"/api/v1/content/{content_id}/publish/instagram",
            headers=headers,
            files={"image": ("photo.png", buf.getvalue(), "image/png")},
        )
        assert r.status_code == 200, r.text
        w, h = Image.open(io.BytesIO(fake_ig.downloaded[0])).size
        assert abs(w / h - 0.8) < 0.01


def test_upload_must_be_an_image(fake_ig) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)
        r = client.post(
            f"/api/v1/content/{content_id}/publish/instagram",
            headers=headers,
            files={"image": ("notes.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "invalid_image"
        assert fake_ig.containers == []


def test_needs_a_public_image_url(fake_ig, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "")
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "instagram"})
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "not_public"


def test_signed_image_link_rejects_other_tokens(fake_ig) -> None:
    with TestClient(app) as client:
        headers = _user(client)
        access_token = headers["Authorization"].split()[1]
        assert client.get(f"/api/v1/social/media/{access_token}").status_code == 404
        assert client.get("/api/v1/social/media/garbage").status_code == 404


def test_caption_limits() -> None:
    instagram.check_caption("ok #a #b")
    with pytest.raises(publishers.PublishError):
        instagram.check_caption(" ".join(f"#t{i}" for i in range(31)))
    with pytest.raises(publishers.PublishError):
        instagram.check_caption("x" * 2201)


def test_expired_token_and_failed_container(fake_ig) -> None:
    fake_ig.publish_error = {"message": "Invalid OAuth access token", "code": 190}
    with TestClient(app) as client:
        headers = _user(client)
        _connect(client, headers)
        content_id = _post(client, headers)
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "instagram"})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "reconnect_required"

        fake_ig.publish_error = None
        fake_ig.container_status = "ERROR"
        r = client.post(f"/api/v1/content/{content_id}/publish", headers=headers, json={"platform": "instagram"})
        assert r.json()["detail"]["code"] == "image_unreachable"
        history = client.get(f"/api/v1/content/{content_id}/publications", headers=headers).json()
        assert [h["status"] for h in history] == ["failed", "failed"]


def test_card_renders_emoji_free_text() -> None:
    data = images.render_card(
        images.CardContent("AI Summit 2026 \U0001f680", "Agents in production", ["One", "Two **bold**"], "12 Nov · Pune")
    )
    assert Image.open(io.BytesIO(data)).size == images.CARD_SIZE
