"""Facebook Pages: Facebook Login for Business and the Page feed.

Docs: https://developers.facebook.com/docs/pages-api/posts

The user signs in with Facebook; EventAI keeps the token of their first Page (Page tokens
made from a long-lived user token do not expire) and posts to that Page's feed.
Permissions: pages_show_list, pages_manage_posts, pages_read_engagement.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.publishers import Identity, OAuthTokens, PublishError, PublishResult, http_client
from app.services.publishers.meta import graph_error
from app.services.publishers.text import plain_text

NAME, LABEL, ENV_HINT = "facebook", "Facebook", "FACEBOOK_APP_ID"
ACCEPTS = frozenset({"linkedin", "instagram"})  # long-form or caption drafts suit a Page post
REFRESH = "none"  # Page tokens from a long-lived user token do not expire
NEEDS_IMAGE = False
MAX_TEXT = 63206
SCOPES = "pages_show_list,pages_manage_posts,pages_read_engagement"
PERMISSION_HINT = (
    "the app needs the pages_manage_posts permission and you must manage the Page"
)


def is_configured() -> bool:
    s = get_settings()
    return bool(s.facebook_app_id and s.facebook_app_secret)


def _graph(path: str) -> str:
    return f"https://graph.facebook.com/{get_settings().facebook_graph_version}/{path.lstrip('/')}"


def authorize_url(state: str, code_challenge: str = "") -> str:
    s = get_settings()
    query = urlencode(
        {
            "client_id": s.facebook_app_id,
            "redirect_uri": s.facebook_redirect_uri,
            "state": state,
            "scope": SCOPES,
            "response_type": "code",
        }
    )
    return f"https://www.facebook.com/{s.facebook_graph_version}/dialog/oauth?{query}"


def build_text(title: str | None, body: str) -> str:
    # Body only: draft titles (e.g. "Instagram Carousel: ...") are labels, not post text.
    return plain_text(body)


def check_text(text: str) -> None:
    if not text.strip():
        raise PublishError("The post is empty", "empty_post")
    if len(text) > MAX_TEXT:
        raise PublishError(f"Facebook posts are limited to {MAX_TEXT} characters.", "too_long")


async def exchange_code(code: str, code_verifier: str = "") -> OAuthTokens:
    """Code -> short-lived user token -> long-lived user token (about 60 days)."""
    s = get_settings()
    try:
        async with http_client() as client:
            res = await client.get(
                _graph("oauth/access_token"),
                params={
                    "client_id": s.facebook_app_id,
                    "client_secret": s.facebook_app_secret,
                    "redirect_uri": s.facebook_redirect_uri,
                    "code": code,
                },
            )
            if res.status_code != 200:
                raise PublishError("Facebook sign-in failed.", "facebook_oauth_failed")
            res = await client.get(
                _graph("oauth/access_token"),
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": s.facebook_app_id,
                    "client_secret": s.facebook_app_secret,
                    "fb_exchange_token": res.json()["access_token"],
                },
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Facebook", "facebook_unreachable") from exc
    if res.status_code != 200:
        raise PublishError("Facebook sign-in failed.", "facebook_oauth_failed")
    data = res.json()
    return OAuthTokens(data["access_token"], data.get("expires_in"), None, None)


async def fetch_identity(access_token: str) -> Identity:
    """The first Page the user manages, with that Page's own token."""
    try:
        async with http_client() as client:
            res = await client.get(
                _graph("me/accounts"),
                params={"fields": "id,name,access_token", "access_token": access_token},
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Facebook", "facebook_unreachable") from exc
    if res.status_code != 200:
        raise PublishError("Could not read your Facebook Pages.", "facebook_oauth_failed")
    pages = [p for p in res.json().get("data", []) if p.get("access_token")]
    if not pages:
        raise PublishError("Your Facebook account manages no Page EventAI may post to.", "no_pages")
    page = pages[0]
    return Identity(str(page["id"]), page.get("name"), access_token=page["access_token"])


async def publish(access_token: str, page_id: str, text: str) -> PublishResult:
    check_text(text)
    try:
        async with http_client() as client:
            res = await client.post(
                _graph(f"{page_id}/feed"), data={"message": text, "access_token": access_token}
            )
    except httpx.HTTPError as exc:
        raise PublishError("Could not reach Facebook", "facebook_unreachable") from exc
    if res.status_code != 200:
        raise graph_error(res, "publish the post", LABEL, PERMISSION_HINT)
    post_id = str(res.json()["id"])  # "<page id>_<post id>"
    return PublishResult(external_post_id=post_id, post_url=f"https://www.facebook.com/{post_id}")
