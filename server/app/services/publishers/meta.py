"""Shared by the Meta platforms (Instagram, Facebook): Graph API error handling."""

from __future__ import annotations

import httpx

from app.services.publishers import PublishError


def graph_error(res: httpx.Response, action: str, label: str, permission_hint: str) -> PublishError:
    """Graph API errors look like {"error": {"message", "code", "error_subcode"}}."""
    try:
        err = res.json().get("error", {})
    except ValueError:
        err = {}
    code = err.get("code")
    message = err.get("message") or res.text[:300] or f"HTTP {res.status_code}"
    if code == 190 or res.status_code == 401:
        return PublishError(
            f"Your {label} connection expired. Reconnect {label} in Settings.", "reconnect_required"
        )
    if code in (10, 200) or res.status_code == 403:
        return PublishError(f"{label} refused: {permission_hint}.", "permission_denied")
    if code in (4, 9, 17, 32, 368, 613) or err.get("error_subcode") == 2207042:
        return PublishError(f"{label}'s publishing limit was reached. Try again later.", "rate_limited")
    return PublishError(f"{label} could not {action}: {str(message)[:300]}", "publish_failed")
