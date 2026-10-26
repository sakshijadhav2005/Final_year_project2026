"""Records when a job had to use fallback output instead of a real model answer.

job_runner starts a record per job; providers and nodes call `mark()` when they fall back
(offline template text, placeholder draft, untranslated copy). LangGraph runs nodes in
tasks that copy the context, and the copies share the same list, so marks reach the job.
"""

from __future__ import annotations

from contextvars import ContextVar

import structlog

logger = structlog.get_logger("degraded")

_EVENTS: ContextVar[list[str] | None] = ContextVar("degraded_events", default=None)


def start() -> list[str]:
    events: list[str] = []
    _EVENTS.set(events)
    return events


def mark(reason: str) -> None:
    logger.warning("degraded_output", reason=reason)
    events = _EVENTS.get()
    if events is not None:
        events.append(reason)
