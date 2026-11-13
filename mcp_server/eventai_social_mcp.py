"""EventAI Social: an MCP server that lets an AI assistant publish approved EventAI drafts.

It is a thin client of the EventAI REST API, signed in as one EventAI user, so every rule
the web app enforces still applies: only that user's own *approved* drafts, only to the
accounts they connected in Settings, no double posting, everything audited.

Tools
- list_social_accounts      which platforms are connected
- list_publishable_drafts   approved drafts, where each can go and whether it is live/scheduled
- preview_post              the exact text (and Instagram image) that would be posted
- publish_post              posts it now or at schedule_at; refuses unless confirm=true
- cancel_scheduled_post     cancels a scheduled post before it is sent
- get_post_status           publish attempts for a draft, with links

Configuration (environment variables)
- EVENTAI_API_URL   default http://localhost:8000
- EVENTAI_EMAIL / EVENTAI_PASSWORD   the EventAI account to act as

Run:  python eventai_social_mcp.py        (stdio transport, for Claude Desktop / Claude Code)
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

Platform = Literal["linkedin", "instagram", "facebook", "x"]
API_PREFIX = "/api/v1"


class EventAIClient:
    """Signs in with email + password and signs in again when the access token expires."""

    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.transport = transport
        self._token: str | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=60.0, transport=self.transport)

    async def _login(self, client: httpx.AsyncClient) -> str:
        if not self.email or not self.password:
            raise ToolError("Set EVENTAI_EMAIL and EVENTAI_PASSWORD for the EventAI account to use.")
        res = await client.post(
            f"{API_PREFIX}/auth/login", json={"email": self.email, "password": self.password}
        )
        if res.status_code != 200:
            raise ToolError("EventAI sign-in failed: check EVENTAI_EMAIL / EVENTAI_PASSWORD.")
        self._token = res.json()["access_token"]
        return self._token

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with self._client() as client:
                token = self._token or await self._login(client)
                res = await client.request(
                    method, f"{API_PREFIX}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs
                )
                if res.status_code == 401:  # access token expired
                    token = await self._login(client)
                    res = await client.request(
                        method, f"{API_PREFIX}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs
                    )
        except httpx.HTTPError as exc:
            raise ToolError(f"Could not reach EventAI at {self.base_url}: {exc}") from exc
        if res.status_code >= 400:
            raise ToolError(_detail(res))
        return res

    async def json(self, method: str, path: str, **kwargs: Any) -> Any:
        return (await self.request(method, path, **kwargs)).json()


def _detail(res: httpx.Response) -> str:
    try:
        detail = res.json().get("detail")
    except ValueError:
        return f"EventAI returned HTTP {res.status_code}"
    if isinstance(detail, dict):
        return str(detail.get("detail") or detail)
    if isinstance(detail, list):  # request validation errors
        return "; ".join(str(d.get("msg", d)) for d in detail)
    return str(detail or f"EventAI returned HTTP {res.status_code}")


def build_server(client: EventAIClient) -> MCPServer:
    server = MCPServer(
        name="eventai-social",
        title="EventAI Social Publishing",
        instructions=(
            "Publishes EventAI drafts that a person already approved to their connected "
            "LinkedIn, Instagram, Facebook Page and X accounts, now or at a scheduled time. "
            "Always call preview_post and show the user the text before publish_post, and "
            "only pass confirm=true after they agree. "
            "Drafts cannot be edited or approved from here; that happens in the EventAI app."
        ),
        version="1.0.0",
    )
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    @server.tool(annotations=read_only)
    async def list_social_accounts() -> list[dict]:
        """Which social platforms the EventAI user has connected, and whether the server supports them."""
        return [
            {
                "platform": item["platform"],
                "drafts_it_takes": item.get("accepts", []),
                "server_configured": item["configured"],
                "connected": bool(item["account"]) and not item["account"]["expired"],
                "account_name": (item["account"] or {}).get("display_name"),
                "connection_expired": bool(item["account"] and item["account"]["expired"]),
            }
            for item in await client.json("GET", "/social/accounts")
        ]

    @server.tool(annotations=read_only)
    async def list_publishable_drafts(platform: Platform | None = None) -> list[dict]:
        """Approved social drafts of the EventAI user, newest first.

        `platforms` maps each platform the draft can go to onto its state: not_published,
        scheduled (with scheduled_for, UTC), posted (with post_url), failed or cancelled.
        """
        params = {"platform": platform} if platform else None
        return await client.json("GET", "/social/drafts", params=params)

    # Unstructured: the result mixes JSON text and an image.
    @server.tool(annotations=read_only, structured_output=False)
    async def preview_post(content_id: str, platform: Platform) -> list[Any]:
        """The exact text that publish_post would send, any problems that would stop it,
        and for Instagram the image that would be posted."""
        preview = await client.json(
            "GET", f"/content/{content_id}/publish-preview", params={"platform": platform}
        )
        result: list[Any] = [
            {k: preview[k] for k in ("platform", "text", "characters", "limit", "problems")}
        ]
        if preview.get("image_preview_path"):
            image = await client.request("GET", preview["image_preview_path"].removeprefix(API_PREFIX))
            result.append(Image(data=image.content, format="jpeg"))
        return result

    @server.tool(
        annotations=ToolAnnotations(
            title="Publish post", read_only_hint=False, destructive_hint=False,
            idempotent_hint=False, open_world_hint=True,
        )
    )
    async def publish_post(
        content_id: str, platform: Platform, confirm: bool = False, schedule_at: str | None = None
    ) -> dict:
        """Publish an approved draft publicly to the user's connected account.

        This posts to a real public account. Show the user preview_post first and set
        confirm=true only after they explicitly agree. `schedule_at` (ISO 8601 with a time
        zone, e.g. 2026-11-20T09:00:00+05:30) schedules it instead, 1 minute to 60 days ahead.
        Instagram uses the generated recap card.
        """
        if not confirm:
            preview = await client.json(
                "GET", f"/content/{content_id}/publish-preview", params={"platform": platform}
            )
            when = f" at {schedule_at}" if schedule_at else ""
            return {
                "published": False,
                "reason": f"Not confirmed. Show this text to the user; if they agree to post it{when}, "
                "call publish_post again with confirm=true.",
                "text": preview["text"],
                "problems": preview["problems"],
            }
        body: dict[str, Any] = {"platform": platform}
        if schedule_at:
            body["scheduled_for"] = schedule_at
        post = await client.json("POST", f"/content/{content_id}/publish", json=body)
        return {
            "published": post["status"] == "posted",
            "scheduled_for": post.get("scheduled_for") if post["status"] == "scheduled" else None,
            "post_id": post.get("id"),
            "platform": post["platform"],
            "post_url": post["post_url"],
            "external_post_id": post["external_post_id"],
        }

    @server.tool(
        annotations=ToolAnnotations(
            title="Cancel scheduled post", read_only_hint=False, destructive_hint=True,
            idempotent_hint=True, open_world_hint=False,
        )
    )
    async def cancel_scheduled_post(post_id: str) -> dict:
        """Cancel a scheduled post (post_id from publish_post or get_post_status) before it is sent."""
        post = await client.json("DELETE", f"/social/posts/{post_id}")
        return {"cancelled": post["status"] == "cancelled", "platform": post["platform"]}

    @server.tool(annotations=read_only)
    async def get_post_status(content_id: str) -> list[dict]:
        """Every publish attempt for a draft (newest first), with links and error messages."""
        return await client.json("GET", f"/content/{content_id}/publications")

    return server


def main() -> None:
    client = EventAIClient(
        base_url=os.environ.get("EVENTAI_API_URL", "http://localhost:8000"),
        email=os.environ.get("EVENTAI_EMAIL", ""),
        password=os.environ.get("EVENTAI_PASSWORD", ""),
    )
    build_server(client).run("stdio")


if __name__ == "__main__":
    main()
