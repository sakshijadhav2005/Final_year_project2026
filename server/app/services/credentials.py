"""Start-up check of provider credentials.

A rejected key is logged loudly once and the engine is skipped by the speech-to-text
fallback chain, instead of every job finding out mid-pipeline. Network problems are not
treated as bad credentials: the engine stays enabled and the result is "unreachable".
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("credentials")

INVALID: set[str] = set()
STATUS: dict[str, str] = {}


def is_invalid(engine: str) -> bool:
    return engine in INVALID


async def _check_gemini(api_key: str) -> str:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"pageSize": 1},
                headers={"x-goog-api-key": api_key},
            )
    except Exception:  # noqa: BLE001 - offline / DNS: unknown, not invalid
        return "unreachable"
    if res.status_code == 200:
        return "ok"
    if res.status_code in (400, 401, 403):
        return "invalid"
    return "unreachable"


def _check_vertex_sync() -> str:
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError, RefreshError
    from google.auth.transport.requests import Request

    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    except DefaultCredentialsError:
        return "invalid"
    try:
        creds.refresh(Request())
    except RefreshError:
        return "invalid"
    except Exception:  # noqa: BLE001
        return "unreachable"
    return "ok"


async def validate_credentials() -> dict[str, str]:
    settings = get_settings()
    checks: dict[str, asyncio.Future | asyncio.Task] = {}
    if settings.gemini_api_key:
        checks["gemini"] = asyncio.ensure_future(_check_gemini(settings.gemini_api_key))
    if settings.google_cloud_project:
        checks["vertex"] = asyncio.ensure_future(
            asyncio.wait_for(asyncio.to_thread(_check_vertex_sync), timeout=20)
        )
    for engine, task in checks.items():
        try:
            status = await task
        except Exception:  # noqa: BLE001 - timeout while refreshing the token
            status = "unreachable"
        STATUS[engine] = status
        if status == "invalid":
            INVALID.add(engine)
            logger.error("credential_invalid", engine=engine, action="engine disabled")
        elif status == "ok":
            INVALID.discard(engine)
            logger.info("credential_ok", engine=engine)
        else:
            logger.warning("credential_unchecked", engine=engine, reason=status)
    return dict(STATUS)
