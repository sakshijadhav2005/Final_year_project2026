"""MCP tools against a fake EventAI API, plus a real stdio handshake."""

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from eventai_social_mcp import EventAIClient, build_server

pytestmark = pytest.mark.anyio

DRAFT = "11111111-1111-1111-1111-111111111111"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeEventAI:
    def __init__(self) -> None:
        self.logins = 0
        self.published: list[dict] = []
        self.expire_next = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/auth/login":
            self.logins += 1
            return httpx.Response(200, json={"access_token": f"tok{self.logins}"})
        if self.expire_next:
            self.expire_next = False
            return httpx.Response(401, json={"detail": {"detail": "expired"}})
        assert request.headers["Authorization"] == f"Bearer tok{self.logins}"
        if path == "/api/v1/social/accounts":
            return httpx.Response(200, json=[
                {"platform": "linkedin", "configured": True,
                 "account": {"display_name": "Asha Rao", "expired": False}},
                {"platform": "instagram", "configured": False, "account": None},
            ])
        if path == "/api/v1/social/drafts":
            return httpx.Response(200, json=[{"content_id": DRAFT, "platform": "linkedin",
                                              "published_url": None}])
        if path == f"/api/v1/content/{DRAFT}/publish-preview":
            platform = request.url.params["platform"]
            return httpx.Response(200, json={
                "platform": platform, "text": "Hello #AI", "characters": 9, "limit": 3000,
                "problems": [],
                "image_preview_path": f"/api/v1/content/{DRAFT}/social-image" if platform == "instagram" else None,
            })
        if path == f"/api/v1/content/{DRAFT}/social-image":
            return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        if path == "/api/v1/social/posts/p1" and request.method == "DELETE":
            return httpx.Response(200, json={"status": "cancelled", "platform": "x"})
        if path == f"/api/v1/content/{DRAFT}/publish":
            payload = json.loads(request.content)
            self.published.append(payload)
            if payload.get("scheduled_for"):
                return httpx.Response(200, json={"id": "p1", "status": "scheduled", "platform": payload["platform"],
                                                 "scheduled_for": payload["scheduled_for"], "post_url": None,
                                                 "external_post_id": None})
            return httpx.Response(200, json={"status": "posted", "platform": "linkedin",
                                             "post_url": "https://www.linkedin.com/feed/update/urn:li:share:1/",
                                             "external_post_id": "urn:li:share:1"})
        if path.endswith("/publish") or path.endswith("/publish-preview"):
            return httpx.Response(409, json={"detail": {"detail": "Approve this draft before publishing it.",
                                                        "code": "not_approved"}})
        return httpx.Response(404, json={"detail": {"detail": "Content not found"}})


@pytest.fixture
def fake():
    return FakeEventAI()


@pytest.fixture
def server(fake):
    return build_server(EventAIClient("http://eventai.test", "a@b.c", "pw", transport=httpx.MockTransport(fake)))


def _payload(result) -> object:
    assert not result.is_error, result
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text)


async def test_tools_listed(server) -> None:
    names = {t.name for t in await server.list_tools()}
    assert names == {"list_social_accounts", "list_publishable_drafts", "preview_post",
                     "publish_post", "cancel_scheduled_post", "get_post_status"}


async def test_accounts_and_drafts(server) -> None:
    accounts = _payload(await server.call_tool("list_social_accounts", {}))
    assert accounts[0] == {"platform": "linkedin", "drafts_it_takes": [], "server_configured": True,
                           "connected": True, "account_name": "Asha Rao", "connection_expired": False}
    drafts = _payload(await server.call_tool("list_publishable_drafts", {"platform": "linkedin"}))
    assert drafts[0]["content_id"] == DRAFT


async def test_publish_needs_confirmation(server, fake) -> None:
    first = _payload(await server.call_tool("publish_post", {"content_id": DRAFT, "platform": "linkedin"}))
    assert first["published"] is False and first["text"] == "Hello #AI"
    assert fake.published == []

    done = _payload(await server.call_tool(
        "publish_post", {"content_id": DRAFT, "platform": "linkedin", "confirm": True}))
    assert done["published"] is True and done["post_url"].startswith("https://www.linkedin.com/")
    assert fake.published == [{"platform": "linkedin"}]


async def test_instagram_preview_includes_image(server) -> None:
    result = await server.call_tool("preview_post", {"content_id": DRAFT, "platform": "instagram"})
    assert not result.is_error
    kinds = [c.type for c in result.content]
    assert "image" in kinds
    image = next(c for c in result.content if c.type == "image")
    assert image.mime_type == "image/jpeg"


async def test_api_errors_become_tool_errors(server) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="Approve this draft"):
        await server.call_tool("publish_post", {"content_id": "other", "platform": "linkedin", "confirm": True})


async def test_expired_session_signs_in_again(server, fake) -> None:
    _payload(await server.call_tool("list_social_accounts", {}))
    fake.expire_next = True
    _payload(await server.call_tool("list_social_accounts", {}))
    assert fake.logins == 2


async def test_stdio_handshake() -> None:
    """The script starts as a real MCP server and answers tools/list over stdio."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("eventai_social_mcp.py"))],
        env={**os.environ, "EVENTAI_API_URL": "http://127.0.0.1:9"},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        assert "publish_post" in {t.name for t in tools.tools}


async def test_schedule_and_cancel(server, fake) -> None:
    done = _payload(await server.call_tool(
        "publish_post",
        {"content_id": DRAFT, "platform": "x", "confirm": True, "schedule_at": "2026-12-01T09:00:00+05:30"},
    ))
    assert done["published"] is False and done["scheduled_for"] == "2026-12-01T09:00:00+05:30"
    assert fake.published[-1] == {"platform": "x", "scheduled_for": "2026-12-01T09:00:00+05:30"}
    cancelled = _payload(await server.call_tool("cancel_scheduled_post", {"post_id": "p1"}))
    assert cancelled == {"cancelled": True, "platform": "x"}
