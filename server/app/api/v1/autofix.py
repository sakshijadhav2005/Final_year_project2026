"""Error-repair agent: the admin review queue, and error reports from the browser."""

import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.db.session import get_db
from app.models.autofix import AUTOFIX_STATUSES, AutoFixIssue
from app.models.user import User
from app.services.audit import write_audit
from app.services.autofix import agent
from app.services.autofix.capture import js_location, record_error

router = APIRouter(prefix="/autofix", tags=["autofix"])

_SUMMARY_FIELDS = (
    "fingerprint", "source", "error_type", "message", "location", "occurrences", "status",
    "status_detail", "attempts", "risk", "cost_usd", "branch", "pr_url",
)


def _summary(row: AutoFixIssue) -> dict:
    data = {k: getattr(row, k) for k in _SUMMARY_FIELDS}
    data["id"] = str(row.id)
    data["title"] = (row.report or {}).get("title")
    for k in ("created_at", "last_seen", "decided_at"):
        value = getattr(row, k)
        data[k] = value.isoformat() if value else None
    return data


def _detail(row: AutoFixIssue) -> dict:
    data = _summary(row)
    for k in ("stack", "context", "report", "diff", "checks", "review", "feedback",
              "base_branch", "base_commit", "decided_by"):
        data[k] = getattr(row, k)
    return data


async def _load(db: AsyncSession, issue_id: UUID) -> AutoFixIssue:
    row = (await db.execute(select(AutoFixIssue).where(AutoFixIssue.id == issue_id))).scalar_one_or_none()
    if row is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "Issue not found", "not_found")
    return row


def _expect(row: AutoFixIssue, *allowed: str) -> None:
    if row.status not in allowed:
        raise http_error(status.HTTP_409_CONFLICT, f"This fix is '{row.status}', not {' or '.join(allowed)}", "conflict")


class DecisionBody(BaseModel):
    reason: str = Field("", max_length=4000)


class ReviseBody(BaseModel):
    feedback: str = Field(..., min_length=3, max_length=4000)


@router.get("/status")
async def autofix_status(_: Annotated[User, Depends(require_admin)]) -> dict:
    settings = get_settings()
    cmd = agent.find_agent_cmd()
    return {
        "active": settings.autofix_active,
        "environment": settings.eventai_env,
        "agent_found": cmd is not None,
        "agent_cmd": cmd,
        "github_cli": agent.gh_cmd() is not None,
        "attempts_today": await agent.attempts_today(),
        "max_per_day": settings.autofix_max_per_day,
        "llm_review": settings.autofix_llm_review,
        "gateway": agent.gateway_status(),
    }


@router.get("/issues")
async def list_issues(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = None,
) -> list[dict]:
    query = select(AutoFixIssue).order_by(AutoFixIssue.last_seen.desc()).limit(200)
    if status_filter in AUTOFIX_STATUSES:
        query = query.where(AutoFixIssue.status == status_filter)
    return [_summary(r) for r in (await db.execute(query)).scalars().all()]


@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: UUID,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return _detail(await _load(db, issue_id))


@router.post("/issues/{issue_id}/approve")
async def approve_issue(
    issue_id: UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await _load(db, issue_id)
    _expect(row, "proposed")
    try:
        row = await agent.approve(row, user.email)
    except RuntimeError as exc:
        raise http_error(status.HTTP_502_BAD_GATEWAY, str(exc), "push_failed") from exc
    await write_audit(db, user_id=user.id, action="autofix_approved", resource_type="autofix",
                      resource_id=str(row.id), detail=row.pr_url)
    await db.commit()
    return _detail(row)


@router.post("/issues/{issue_id}/reject")
async def reject_issue(
    issue_id: UUID,
    body: DecisionBody,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await _load(db, issue_id)
    _expect(row, "proposed", "failed", "new", "external")
    row = await agent.reject(row, user.email, body.reason)
    await write_audit(db, user_id=user.id, action="autofix_rejected", resource_type="autofix",
                      resource_id=str(row.id), detail=body.reason[:500] or None)
    await db.commit()
    return _detail(row)


@router.post("/issues/{issue_id}/revise")
async def revise_issue(
    issue_id: UUID,
    body: ReviseBody,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await _load(db, issue_id)
    _expect(row, "proposed")
    row.status, row.feedback, row.status_detail = "revising", body.feedback, "Queued: applying your feedback"
    await db.commit()
    return _detail(row)


@router.post("/issues/{issue_id}/retry")
async def retry_issue(
    issue_id: UUID,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await _load(db, issue_id)
    _expect(row, "failed", "rejected", "external")
    row.status, row.status_detail = "new", "Queued for the agent"
    await db.commit()
    return _detail(row)


class ClientError(BaseModel):
    name: str = Field("Error", max_length=128)
    message: str = Field(..., max_length=4000)
    stack: str | None = Field(None, max_length=20000)
    page: str | None = Field(None, max_length=512)


_client_hits: list[float] = []


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
async def client_error(body: ClientError, request: Request) -> None:
    """Browser errors (development only). No login needed: errors also happen signed out."""
    if not get_settings().autofix_active:
        return
    now = time.monotonic()
    _client_hits[:] = [t for t in _client_hits if now - t < 60]
    if len(_client_hits) >= 30:  # an error in a render loop must not flood the queue
        return
    _client_hits.append(now)
    await record_error(
        source="frontend",
        error_type=body.name or "Error",
        message=body.message,
        stack=body.stack,
        location=js_location(body.stack),
        context={"page": (body.page or "").split("?")[0], "browser": request.headers.get("user-agent", "")[:200]},
    )
