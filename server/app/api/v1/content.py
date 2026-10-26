import json
import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import http_error
from app.core.security import UserRole
from app.db.session import get_db
from app.models.content import ContentPiece
from app.models.job import Job
from app.models.user import User
from app.schemas.common import ContentPatch, ContentPublic, CreatePostRequest, RejectRequest
from app.services.audit import write_audit

router = APIRouter(tags=["content"])


PUBLIC_STATUSES = ("approved", "ready_to_publish")


def _can_access_job(user: User, job: Job) -> bool:
    return user.role == UserRole.ADMIN or job.user_id == user.id


async def _load_piece(
    db: AsyncSession, user: User, content_id: UUID, *, write: bool = False
) -> ContentPiece:
    """Load a content piece and enforce ownership.

    - Job content: only the job owner (or an admin) may read drafts or change it.
    - Community posts (no job): the author (or an admin) may change it.
    - Anyone signed in may *read* content that a human already approved.
    """
    piece = (
        await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    ).scalar_one_or_none()
    if piece is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "Content not found", "not_found")
    if user.role == UserRole.ADMIN:
        return piece

    job = None
    if piece.job_id is not None:
        job = (await db.execute(select(Job).where(Job.id == piece.job_id))).scalar_one_or_none()
    is_owner = (job is not None and job.user_id == user.id) or (
        job is None and piece.user_id == user.id
    )
    if is_owner:
        return piece
    if not write and piece.status in PUBLIC_STATUSES:
        return piece
    raise http_error(status.HTTP_404_NOT_FOUND, "Content not found", "not_found")


@router.get("/content", response_model=list[ContentPublic])
async def list_community_content(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    event_id: UUID | None = None,
    type: str | None = None,
) -> list[ContentPiece]:
    query = select(ContentPiece).order_by(ContentPiece.created_at.desc())
    if user.role != UserRole.ADMIN:
        # Unapproved AI drafts stay private to their owner (human-in-the-loop gate).
        query = query.where(
            or_(ContentPiece.status.in_(PUBLIC_STATUSES), ContentPiece.user_id == user.id)
        )
    if event_id is not None:
        query = query.where(ContentPiece.event_id == event_id)
    if type is not None:
        query = query.where(ContentPiece.type == type)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/content", response_model=ContentPublic, status_code=status.HTTP_201_CREATED)
async def create_user_post(
    body: CreatePostRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContentPiece:
    author_name = user.email.split("@")[0]
    piece = ContentPiece(
        job_id=None,  # community posts are written by people, not by a pipeline job
        title=body.title,
        body=body.body,
        type=body.type,
        event_id=body.event_id,
        user_id=user.id,
        author_name=author_name,
        status="approved",
        language="en",
    )
    db.add(piece)
    await db.commit()
    await db.refresh(piece)
    return piece


@router.get("/jobs/{job_id}/content", response_model=list[ContentPublic])
async def list_job_content(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ContentPiece]:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None or not _can_access_job(user, job):
        raise http_error(status.HTTP_404_NOT_FOUND, "Job not found", "not_found")
    result = await db.execute(select(ContentPiece).where(ContentPiece.job_id == job_id))
    return list(result.scalars().all())


@router.get("/content/{content_id}", response_model=ContentPublic)
async def get_content(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContentPiece:
    return await _load_piece(db, user, content_id)


@router.patch("/content/{content_id}", response_model=ContentPublic)
async def patch_content(
    content_id: UUID,
    body: ContentPatch,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContentPiece:
    piece = await _load_piece(db, user, content_id, write=True)
    if body.title is not None:
        piece.title = body.title
    if body.body is not None:
        piece.body = body.body
    await db.commit()
    await db.refresh(piece)
    return piece


@router.post("/content/{content_id}/approve", response_model=ContentPublic)
async def approve_content(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContentPiece:
    piece = await _load_piece(db, user, content_id, write=True)
    piece.status = "approved"
    await write_audit(
        db,
        user_id=user.id,
        action="approve",
        resource_type="content",
        resource_id=str(piece.id),
    )
    # Community/user posts are not attached to a job, so only roll up job status when present.
    job = None
    if piece.job_id is not None:
        job = (
            await db.execute(select(Job).where(Job.id == piece.job_id))
        ).scalar_one_or_none()
    if job is not None:
        remaining = await db.execute(
            select(ContentPiece).where(
                ContentPiece.job_id == job.id,
                ContentPiece.status == "pending_review",
                ContentPiece.id != piece.id,
            )
        )
        if remaining.scalars().first() is None:
            job.status = "ready_to_publish"
    await db.commit()
    await db.refresh(piece)
    return piece


@router.post("/content/{content_id}/reject", response_model=ContentPublic)
async def reject_content(
    content_id: UUID,
    body: RejectRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContentPiece:
    piece = await _load_piece(db, user, content_id, write=True)
    piece.status = "rejected"
    await write_audit(
        db,
        user_id=user.id,
        action="reject",
        resource_type="content",
        resource_id=str(piece.id),
        detail=body.reason,
    )
    await db.commit()
    await db.refresh(piece)
    return piece


@router.get("/content/{content_id}/download")
async def download_content(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: Literal["markdown", "text", "json"] = "markdown",
) -> Response:
    """Export a content piece as Markdown, plain text or JSON."""
    piece = await _load_piece(db, user, content_id)
    title = piece.title or piece.type.replace("_", " ").title()
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_")[:60] or "content"
    if format == "json":
        payload = ContentPublic.model_validate(piece).model_dump(mode="json")
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
        )
    if format == "text":
        plain = re.sub(r"[#*_`>]+", "", piece.body or "")
        return Response(
            content=f"{title}\n\n{plain.strip()}\n",
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.txt"'},
        )
    return Response(
        content=f"# {title}\n\n{(piece.body or '').strip()}\n",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.md"'},
    )
