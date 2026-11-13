"""X (Twitter): OAuth 2.0 with PKCE and the v2 "create post" endpoint.

Docs: https://docs.x.com/resources/fundamentals/authentication/oauth-2-0/authorization-code
      https://docs.x.com/x-api/posts/create-post

The app must be a confidential client ("Web App") with read and write permissions.
Access tokens last 2 hours; ``offline.access`` gives a refresh token (rotated on use).
Posting needs an X API plan that includes write access.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.publishers import Identity, OAuthTokens, PublishError, PublishResult, http_client
from app.services.publishers.text import plain_text

NAME, LABEL, ENV_HINT = "x", "X", "X_CLIENT_ID"
ACCEPTS = frozenset({"x"})  # only short drafts written for X
REFRESH = "refresh_token"
NEEDS_IMAGE = False
MAX_TEXT = 280
URL_WEIGHT = 23  # every link counts as 23 characters (t.co)

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
ME_URL = "https://api.x.com/2/users/me"
POSTS_URL = "https://api.x.com/2/tweets"
SCOPES = "tweet.read tweet.write users.read offline.access"

_URL = re.compile(r"https?://\S+")


def is_configured() -> bool:
    s = get_settings()
    return bool(s.x_client_id and s.x_client_secret)


def authorize_url(state: str, code_challenge: str = "") -> str:
    s = get_settings()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": s.x_client_id,
            "redirect_uri": s.x_redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _char_weight(ch: str) -> int:
    cp = ord(ch)
    light = cp <= 0x10FF or 0x2000 <= cp <= 0x200D or 0x2010 <= cp <= 0x201F or 0x2032 <= cp <= 0x2037
    return 1 if light else 2


def weighted_length(text: str) -> int:
    """X's counting: links are 23, CJK and emoji count double (twitter-text v3 ranges)."""
    text = unicodedata.normalize("NFC", text)
    total, pos = 0, 0
    for match in _URL.finditer(text):
        total += sum(_char_weight(c) for c in text[pos : match.start()]) + URL_WEIGHT
        pos = match.end()
    return total + sum(_char_weight(c) for c in text[pos:])


def build_text(title: str | None, body: str) -> str:
    return plain_text(body)


def check_text(text: str) -> None:
    if not text.strip():
        raise PublishError("The post is empty", "empty_post")
    length = weighted_length(text)
    if length > MAX_TEXT:
        raise PublishError(
            f"X posts are limited to {MAX_TEXT} characters; this one counts {length}. "
            "Shorten it and try again.",
            "too_long",
        )


def _basic_auth() -> httpx.BasicAuth:
    s = get_settings()
    return httpx.BasicAuth(s.x_client_id, s.x_client_secret)


def _error_message(res: httpx.Response) -> str:
    try:
        data = res.json()
    except ValueError:
        return res.text[:300] or f"HTTP {res.status_code}"
    if isinstance(data.get("errors"), list) and data["errors"]:
        return str(data["errors"][0].get("message") or data["errors"][0])[:300]
    return str(data.get("detail") or data.get("error_description") or data.get("title") or data)[:300]


async def _token_request(form: dict) -> OAuthTokens:
    try:
        async with http_client() as client:
            res = await client.post(TOKEN_URL, data=form, auth=_basic_auth())
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach X", "x_unreachable") from exc
    if res.status_code != 200:
        if form["grant_type"] == "refresh_token":
            raise PublishError("Your X connection expired. Reconnect X in Settings.", "reconnect_required")
        raise PublishError(f"X sign-in failed: {_error_message(res)}", "x_oauth_failed")
    data = res.json()
    return OAuthTokens(
        access_token=data["access_token"],
        expires_in=data.get("expires_in"),
        refresh_token=data.get("refresh_token"),
        scope=data.get("scope"),
    )


async def exchange_code(code: str, code_verifier: str = "") -> OAuthTokens:
    if not code_verifier:
        raise PublishError("X sign-in failed: missing PKCE verifier.", "x_oauth_failed")
    s = get_settings()
    return await _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": s.x_redirect_uri,
            "code_verifier": code_verifier,
            "client_id": s.x_client_id,
        }
    )


async def refresh(refresh_token: str) -> OAuthTokens:
    tokens = await _token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": get_settings().x_client_id}
    )
    if not tokens.refresh_token:  # X rotates refresh tokens; keep the old one if none came back
        tokens.refresh_token = refresh_token
    return tokens


async def fetch_identity(access_token: str) -> Identity:
    try:
        async with http_client() as client:
            res = await client.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"})
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach X", "x_unreachable") from exc
    if res.status_code != 200:
        raise PublishError(f"Could not read your X profile: {_error_message(res)}", "x_oauth_failed")
    data = res.json()["data"]
    return Identity(str(data["id"]), f"@{data['username']}" if data.get("username") else data.get("name"))


async def publish(access_token: str, user_id: str, text: str) -> PublishResult:
    check_text(text)
    try:
        async with http_client() as client:
            res = await client.post(
                POSTS_URL, json={"text": text}, headers={"Authorization": f"Bearer {access_token}"}
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach X", "x_unreachable") from exc
    if res.status_code == 401:
        raise PublishError("Your X connection expired. Reconnect X in Settings.", "reconnect_required")
    if res.status_code == 402:
        raise PublishError(
            "X refused the post: your X API plan does not include posting (credits or a paid tier).",
            "permission_denied",
        )
    if res.status_code == 403:
        raise PublishError(f"X refused the post: {_error_message(res)}", "permission_denied")
    if res.status_code == 429:
        raise PublishError("X rate limit reached. Try again later.", "rate_limited")
    if res.status_code not in (200, 201):
        raise PublishError(f"X rejected the post: {_error_message(res)}", "publish_failed")
    post_id = str(res.json()["data"]["id"])
    return PublishResult(external_post_id=post_id, post_url=f"https://x.com/i/web/status/{post_id}")
