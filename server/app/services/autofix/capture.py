"""Record errors for the repair agent: one row per distinct error (fingerprint)."""

import hashlib
import re
import traceback
from datetime import UTC, datetime
from pathlib import PurePosixPath

import structlog
from sqlalchemy import select

from app.core.config import get_settings

logger = structlog.get_logger("autofix")

# Errors from the outside world: a code change will not fix them.
_EXTERNAL_TYPES = {
    "ResourceExhausted", "ServiceUnavailable", "DeadlineExceeded", "PermissionDenied",
    "Unauthenticated", "DefaultCredentialsError", "RefreshError", "ConnectionError",
    "ConnectError", "ConnectTimeout", "ReadTimeout", "TimeoutError", "RateLimitError",
    "APIConnectionError", "APITimeoutError", "AuthenticationError", "OverloadedError",
    "InternalServerError", "ClientConnectorError", "ServerDisconnectedError",
}
_EXTERNAL_TEXT = re.compile(
    r"\b(429|503|quota|rate.?limit|resource.?exhausted|api key not valid|invalid api key|"
    r"credentials|could not connect|connection refused|name or service not known|"
    r"getaddrinfo|timed out|overloaded|service unavailable|no space left)\b",
    re.IGNORECASE,
)

_SECRET_FIELD = re.compile(r"(key|secret|token|password|dsn)", re.IGNORECASE)
_SECRET_PATTERNS = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [redacted]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[jwt]"),
    (re.compile(r"\b(sk-ant-|sk-|AIza|ghp_|gho_|github_pat_)[A-Za-z0-9_-]{10,}"), "[api-key]"),
    (re.compile(r"(?i)([?&](?:token|access_token|key)=)[^&\s\"']+"), r"\1[redacted]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|mysql(?:\+\w+)?|redis)://[^\s\"']+"), r"\1://[redacted]"),
]

# Our own code. Frames outside it (libraries) are context, not the place to fix.
_PROJECT_PARTS = ("server/app/", "client/src/", "/app/", "/src/")
_SELF = "services/autofix/"


def redact(text: str | None) -> str:
    """Remove secret values from anything that will be stored or sent to the agent."""
    if not text:
        return ""
    settings = get_settings()
    for name, value in settings.model_dump().items():
        if isinstance(value, str) and len(value) >= 6 and _SECRET_FIELD.search(name):
            text = text.replace(value, f"[{name}]")
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def is_external(error_type: str, message: str) -> bool:
    return error_type in _EXTERNAL_TYPES or bool(_EXTERNAL_TEXT.search(message or ""))


def _relative(path: str) -> str:
    p = path.replace("\\", "/")
    for marker in ("server/app/", "client/src/"):
        if marker in p:
            return marker + p.split(marker, 1)[1]
    m = re.search(r"/src/([^?:]+)", p)  # a Vite dev URL: http://localhost:5173/src/x.tsx?t=1
    if m:
        return "client/src/" + m.group(1)
    return PurePosixPath(p).name


def _in_project(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(part in p for part in _PROJECT_PARTS) and ".venv" not in p and "node_modules" not in p


def python_location(exc: BaseException) -> str | None:
    """file:function of the deepest frame in our own code."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if _in_project(f.filename)]
    if not frames:
        return None
    last = frames[-1]
    return f"{_relative(last.filename)}:{last.name}"


_JS_FRAME = re.compile(r"(?:at\s+(?P<fn>[\w$.<>]+)\s+\()?(?P<url>(?:https?://|/)[^\s()]+?):\d+:\d+")


def js_location(stack: str | None) -> str | None:
    for line in (stack or "").splitlines():
        m = _JS_FRAME.search(line)
        if m and _in_project(m.group("url")):
            return f"{_relative(m.group('url'))}:{m.group('fn') or '<anonymous>'}"
    return None


def fingerprint(error_type: str, location: str | None, message: str) -> str:
    # Same type at the same place = same bug. Without a location, fall back to the
    # message with numbers and ids removed so repeats still group.
    key = location or re.sub(r"[0-9a-f]{8,}|\d+", "#", message)[:200]
    return hashlib.sha1(f"{error_type}|{key}".encode()).hexdigest()[:16]


async def record_error(
    *,
    source: str,
    error_type: str,
    message: str,
    stack: str | None = None,
    location: str | None = None,
    context: dict | None = None,
) -> None:
    """Store an error (or count a repeat). Never raises: reporting must not break the app."""
    if not get_settings().autofix_active:
        return
    if location and _SELF in location:
        return  # never let the repair agent try to repair itself in a loop
    try:
        from app.db.session import SessionLocal
        from app.models.autofix import AutoFixIssue

        message = redact(message)[:4000]
        fp = fingerprint(error_type, location, message)
        now = datetime.now(UTC)
        async with SessionLocal() as db:
            row = (
                await db.execute(select(AutoFixIssue).where(AutoFixIssue.fingerprint == fp))
            ).scalar_one_or_none()
            if row is not None:
                row.occurrences += 1
                row.last_seen = now
            else:
                external = is_external(error_type, message)
                db.add(
                    AutoFixIssue(
                        fingerprint=fp,
                        source=source,
                        error_type=error_type[:128],
                        message=message,
                        location=location,
                        stack=redact(stack)[-12000:] or None,
                        context={k: redact(str(v))[:1000] for k, v in (context or {}).items()},
                        last_seen=now,
                        status="external" if external else "new",
                        status_detail=(
                            "Looks like a service, network or credentials problem, not a code bug. "
                            "Check the provider status, your quota and the keys in .env."
                            if external else None
                        ),
                    )
                )
                logger.info("autofix_error_recorded", fingerprint=fp, source=source, external=external)
            await db.commit()
    except Exception as exc:  # pragma: no cover - reporting is best effort
        logger.warning("autofix_record_failed", error=str(exc))


async def record_exception(exc: BaseException, *, source: str, context: dict | None = None) -> None:
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    await record_error(
        source=source,
        error_type=type(exc).__name__,
        message=str(exc) or type(exc).__name__,
        stack=stack,
        location=python_location(exc),
        context=context,
    )
