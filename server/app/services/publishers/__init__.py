"""Publish approved content to the user's own social media accounts.

One module per platform. Each exposes the OAuth helpers (authorize URL, code exchange)
and a ``publish`` coroutine that returns a :class:`PublishResult` or raises
:class:`PublishError`. The API layer owns the database; these modules only talk HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

# Tests swap this for an ``httpx.MockTransport`` so no request leaves the machine.
HTTP_TRANSPORT: httpx.AsyncBaseTransport | None = None

SUPPORTED_PLATFORMS = ("linkedin",)


class PublishError(Exception):
    """A platform rejected the request. ``code`` is stable for the UI; the message is for people."""

    def __init__(self, message: str, code: str = "publish_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class PublishResult:
    external_post_id: str
    post_url: str | None


@dataclass
class OAuthTokens:
    access_token: str
    expires_in: int | None
    refresh_token: str | None
    scope: str | None


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15.0, transport=HTTP_TRANSPORT)
