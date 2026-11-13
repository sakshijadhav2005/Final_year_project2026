"""Instagram: "Instagram API with Instagram Login" and the Content Publishing API.

Works with Instagram **Business or Creator** accounts; no Facebook Page is needed.
Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login

Publishing is two steps: create a media container from a *public* JPEG URL (Instagram
downloads the image itself), wait until it is ready, then publish the container.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.publishers import OAuthTokens, PublishError, PublishResult, http_client
from app.services.publishers.text import HASHTAG, MENTION, plain_text

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
SCOPES = "instagram_business_basic,instagram_business_content_publish"

MAX_CAPTION_CHARS = 2200
MAX_HASHTAGS = 30
MAX_MENTIONS = 20
CONTAINER_POLL_SECONDS = 2.0
CONTAINER_POLL_ATTEMPTS = 15
# Long-lived tokens last 60 days and can be refreshed once they are a day old.
REFRESH_WHEN_LEFT = timedelta(days=10)


def is_configured() -> bool:
    s = get_settings()
    return bool(s.instagram_client_id and s.instagram_client_secret)


def _graph(path: str) -> str:
    return f"{GRAPH}/{get_settings().instagram_graph_version}/{path.lstrip('/')}"


def authorize_url(state: str) -> str:
    s = get_settings()
    query = urlencode(
        {
            "client_id": s.instagram_client_id,
            "redirect_uri": s.instagram_redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def build_caption(body: str) -> str:
    return plain_text(body)


def check_caption(caption: str) -> None:
    if len(caption) > MAX_CAPTION_CHARS:
        raise PublishError(
            f"Instagram captions are limited to {MAX_CAPTION_CHARS} characters; "
            f"this one has {len(caption)}. Shorten it and try again.",
            "too_long",
        )
    tags = len(HASHTAG.findall(caption))
    if tags > MAX_HASHTAGS:
        raise PublishError(
            f"Instagram allows at most {MAX_HASHTAGS} hashtags; this caption has {tags}.", "too_long"
        )
    mentions = len(MENTION.findall(caption))
    if mentions > MAX_MENTIONS:
        raise PublishError(
            f"Instagram allows at most {MAX_MENTIONS} @mentions; this caption has {mentions}.",
            "too_long",
        )


def _graph_error(res: httpx.Response, action: str) -> PublishError:
    try:
        err = res.json().get("error", {})
    except ValueError:
        err = {}
    code, message = err.get("code"), err.get("message") or res.text[:300] or f"HTTP {res.status_code}"
    if code == 190 or res.status_code == 401:
        return PublishError(
            "Your Instagram connection expired. Reconnect Instagram in Settings.", "reconnect_required"
        )
    if code in (10, 200) or res.status_code == 403:
        return PublishError(
            "Instagram refused: the app needs the instagram_business_content_publish permission, "
            "and the account must be a Business or Creator account.",
            "permission_denied",
        )
    if code in (4, 9, 17, 32, 613) or err.get("error_subcode") == 2207042:
        return PublishError("Instagram's publishing limit was reached. Try again later.", "rate_limited")
    return PublishError(f"Instagram could not {action}: {str(message)[:300]}", "publish_failed")


async def exchange_code(code: str) -> OAuthTokens:
    """Code -> short-lived token (1 hour) -> long-lived token (60 days)."""
    s = get_settings()
    code = code.removesuffix("#_")  # Instagram appends this to the redirect
    try:
        async with http_client() as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "client_id": s.instagram_client_id,
                    "client_secret": s.instagram_client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": s.instagram_redirect_uri,
                    "code": code,
                },
            )
            if res.status_code != 200:
                raise PublishError("Instagram sign-in failed.", "instagram_oauth_failed")
            data = res.json()
            if isinstance(data.get("data"), list) and data["data"]:
                data = data["data"][0]
            short_token = data["access_token"]
            res = await client.get(
                f"{GRAPH}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": s.instagram_client_secret,
                    "access_token": short_token,
                },
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Instagram", "instagram_unreachable") from exc
    if res.status_code != 200:
        raise PublishError("Instagram sign-in failed.", "instagram_oauth_failed")
    long_lived = res.json()
    return OAuthTokens(
        access_token=long_lived["access_token"],
        expires_in=long_lived.get("expires_in"),
        refresh_token=None,  # the long-lived token refreshes itself (see refresh())
        scope=data.get("permissions") if isinstance(data.get("permissions"), str) else None,
    )


async def refresh(access_token: str) -> OAuthTokens:
    try:
        async with http_client() as client:
            res = await client.get(
                f"{GRAPH}/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": access_token},
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Instagram", "instagram_unreachable") from exc
    if res.status_code != 200:
        raise _graph_error(res, "refresh the connection")
    data = res.json()
    return OAuthTokens(data["access_token"], data.get("expires_in"), None, None)


def needs_refresh(expires_at: datetime | None) -> bool:
    return expires_at is not None and expires_at - datetime.now(UTC) < REFRESH_WHEN_LEFT


async def fetch_identity(access_token: str) -> tuple[str, str | None]:
    """(Instagram professional account id, @username)."""
    try:
        async with http_client() as client:
            res = await client.get(
                _graph("me"), params={"fields": "user_id,username", "access_token": access_token}
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Instagram", "instagram_unreachable") from exc
    if res.status_code != 200:
        raise PublishError("Could not read your Instagram account.", "instagram_oauth_failed")
    data = res.json()
    username = data.get("username")
    return str(data.get("user_id") or data["id"]), f"@{username}" if username else None


async def publish(access_token: str, ig_user_id: str, image_url: str, caption: str) -> PublishResult:
    check_caption(caption)
    auth = {"access_token": access_token}
    try:
        async with http_client() as client:
            res = await client.post(
                _graph(f"{ig_user_id}/media"), data={"image_url": image_url, "caption": caption, **auth}
            )
            if res.status_code != 200:
                raise _graph_error(res, "use the image")
            container = res.json()["id"]

            for _ in range(CONTAINER_POLL_ATTEMPTS):
                res = await client.get(_graph(container), params={"fields": "status_code", **auth})
                if res.status_code != 200:
                    raise _graph_error(res, "prepare the post")
                state = res.json().get("status_code")
                if state in ("FINISHED", "PUBLISHED"):
                    break
                if state in ("ERROR", "EXPIRED"):
                    raise PublishError(
                        "Instagram could not download or process the image. It must be a public "
                        "JPEG URL that Instagram's servers can reach.",
                        "image_unreachable",
                    )
                await asyncio.sleep(CONTAINER_POLL_SECONDS)
            else:
                raise PublishError("Instagram took too long to prepare the post. Try again.", "timeout")

            res = await client.post(_graph(f"{ig_user_id}/media_publish"), data={"creation_id": container, **auth})
            if res.status_code != 200:
                raise _graph_error(res, "publish the post")
            media_id = str(res.json()["id"])

            permalink = None
            res = await client.get(_graph(media_id), params={"fields": "permalink", **auth})
            if res.status_code == 200:
                permalink = res.json().get("permalink")
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Instagram", "instagram_unreachable") from exc
    return PublishResult(external_post_id=media_id, post_url=permalink)
