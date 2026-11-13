"""LinkedIn: OAuth 2.0 (3-legged) and member posts through the versioned Posts API.

Docs:
- OAuth: https://learn.microsoft.com/linkedin/shared/authentication/authorization-code-flow
- Posts API: https://learn.microsoft.com/linkedin/marketing/community-management/shares/posts-api
- Text format ("little text"): https://learn.microsoft.com/linkedin/marketing/community-management/shares/little-text-format

Scopes: ``openid profile`` (who connected, from the OpenID Connect product) and
``w_member_social`` (post as that member, from the "Share on LinkedIn" product).
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.publishers import OAuthTokens, PublishError, PublishResult, http_client

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
SCOPES = "openid profile w_member_social"

MAX_COMMENTARY_CHARS = 3000

# Characters with meaning in LinkedIn's "little text" format; plain text must escape them.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"(?<![\w&/])#(\w+)")


def is_configured() -> bool:
    s = get_settings()
    return bool(s.linkedin_client_id and s.linkedin_client_secret)


def authorize_url(state: str) -> str:
    s = get_settings()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": s.linkedin_client_id,
            "redirect_uri": s.linkedin_redirect_uri,
            "state": state,
            "scope": SCOPES,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _plain_text(markdown: str) -> str:
    """LinkedIn shows text as typed, so drop Markdown markers the writers may produce."""
    text = markdown.replace("\r\n", "\n")
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)  # bold
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", text)  # links
    text = re.sub(r"^(\s*)[*-]\s+", r"\1• ", text, flags=re.MULTILINE)  # bullets
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_post_text(title: str | None, body: str) -> str:
    """The post as the reader will see it (before little-text escaping)."""
    text = _plain_text(body)
    if title and title.strip() and not text.lower().startswith(title.strip().lower()):
        text = f"{title.strip()}\n\n{text}"
    return text


def to_commentary(text: str) -> str:
    """Escape reserved characters; keep #tags clickable as LinkedIn hashtags."""
    out: list[str] = []
    pos = 0
    for match in _HASHTAG.finditer(text):
        out.append(_RESERVED.sub(r"\\\1", text[pos : match.start()]))
        out.append("{hashtag|\\#|" + match.group(1) + "}")
        pos = match.end()
    out.append(_RESERVED.sub(r"\\\1", text[pos:]))
    return "".join(out)


def _error_message(res: httpx.Response) -> str:
    try:
        payload = res.json()
    except ValueError:
        return res.text[:300] or f"HTTP {res.status_code}"
    return str(
        payload.get("message") or payload.get("error_description") or payload.get("error") or payload
    )[:300]


async def exchange_code(code: str) -> OAuthTokens:
    s = get_settings()
    try:
        async with http_client() as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": s.linkedin_redirect_uri,
                    "client_id": s.linkedin_client_id,
                    "client_secret": s.linkedin_client_secret,
                },
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach LinkedIn", "linkedin_unreachable") from exc
    if res.status_code != 200:
        raise PublishError(f"LinkedIn sign-in failed: {_error_message(res)}", "linkedin_oauth_failed")
    data = res.json()
    return OAuthTokens(
        access_token=data["access_token"],
        expires_in=data.get("expires_in"),
        refresh_token=data.get("refresh_token"),
        scope=data.get("scope"),
    )


async def refresh(refresh_token: str) -> OAuthTokens:
    """Only apps LinkedIn approved for programmatic refresh get refresh tokens."""
    s = get_settings()
    try:
        async with http_client() as client:
            res = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": s.linkedin_client_id,
                    "client_secret": s.linkedin_client_secret,
                },
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach LinkedIn", "linkedin_unreachable") from exc
    if res.status_code != 200:
        raise PublishError(
            "Your LinkedIn connection expired. Reconnect LinkedIn in Settings.", "reconnect_required"
        )
    data = res.json()
    return OAuthTokens(
        access_token=data["access_token"],
        expires_in=data.get("expires_in"),
        refresh_token=data.get("refresh_token", refresh_token),
        scope=data.get("scope"),
    )


async def fetch_member(access_token: str) -> tuple[str, str | None]:
    """(member id, display name) of the account that just connected."""
    try:
        async with http_client() as client:
            res = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach LinkedIn", "linkedin_unreachable") from exc
    if res.status_code != 200:
        raise PublishError(
            f"Could not read your LinkedIn profile: {_error_message(res)}", "linkedin_oauth_failed"
        )
    data = res.json()
    return str(data["sub"]), data.get("name")


async def publish(access_token: str, member_id: str, text: str) -> PublishResult:
    """Post ``text`` (plain, from :func:`build_post_text`) to the member's feed."""
    if not text.strip():
        raise PublishError("The post is empty", "empty_post")
    if len(text) > MAX_COMMENTARY_CHARS:
        raise PublishError(
            f"LinkedIn posts are limited to {MAX_COMMENTARY_CHARS} characters; "
            f"this one has {len(text)}. Shorten it and try again.",
            "too_long",
        )
    body = {
        "author": f"urn:li:person:{member_id}",
        "commentary": to_commentary(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": get_settings().linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    try:
        async with http_client() as client:
            res = await client.post(POSTS_URL, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach LinkedIn", "linkedin_unreachable") from exc
    if res.status_code == 401:
        raise PublishError(
            "Your LinkedIn connection expired. Reconnect LinkedIn in Settings.", "reconnect_required"
        )
    if res.status_code == 403:
        raise PublishError(
            "LinkedIn refused the post: the app needs the w_member_social permission "
            "(\"Share on LinkedIn\" product). Reconnect after enabling it.",
            "permission_denied",
        )
    if res.status_code == 429:
        raise PublishError("LinkedIn rate limit reached. Try again later.", "rate_limited")
    if res.status_code not in (200, 201):
        raise PublishError(f"LinkedIn rejected the post: {_error_message(res)}", "publish_failed")

    urn = res.headers.get("x-restli-id") or res.headers.get("x-linkedin-id") or ""
    if not urn:
        try:
            urn = str(res.json().get("id") or "")
        except ValueError:
            urn = ""
    url = f"https://www.linkedin.com/feed/update/{urn}/" if urn.startswith("urn:li:") else None
    return PublishResult(external_post_id=urn or "unknown", post_url=url)
