import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
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


def _can_access_job(user: User, job: Job) -> bool:
    return user.role == UserRole.ADMIN or job.user_id == user.id


async def _load_piece(db: AsyncSession, user: User, content_id: UUID) -> ContentPiece:
    piece = (
        await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    ).scalar_one_or_none()
    if piece is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "Content not found", "not_found")
    if piece.job_id is not None:
        job = (await db.execute(select(Job).where(Job.id == piece.job_id))).scalar_one_or_none()
        if job and not _can_access_job(user, job):
            raise http_error(status.HTTP_404_NOT_FOUND, "Content not found", "not_found")
        if (
            job is None
            and piece.user_id is not None
            and user.role != UserRole.ADMIN
            and piece.user_id != user.id
        ):
            raise http_error(status.HTTP_404_NOT_FOUND, "Content not found", "not_found")
    elif piece.user_id is not None:
        if user.role != UserRole.ADMIN and piece.user_id != user.id:
            raise http_error(status.HTTP_404_NOT_FOUND, "Content not found", "not_found")
    return piece


@router.get("/content", response_model=list[ContentPublic])
async def list_community_content(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    event_id: UUID | None = None,
    type: str | None = None,
) -> list[ContentPiece]:
    query = select(ContentPiece).order_by(ContentPiece.created_at.desc())
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
    import uuid

    author_name = user.email.split("@")[0]
    piece = ContentPiece(
        job_id=uuid.uuid4(),
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
    piece = await _load_piece(db, user, content_id)
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
    piece = await _load_piece(db, user, content_id)
    piece.status = "approved"
    await write_audit(
        db,
        user_id=user.id,
        action="approve",
        resource_type="content",
        resource_id=str(piece.id),
    )
    job = (await db.execute(select(Job).where(Job.id == piece.job_id))).scalar_one()
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
    piece = await _load_piece(db, user, content_id)
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
    format: str = Query("markdown", description="Export format: markdown, text, or json"),
) -> Response:
    piece = await _load_piece(db, user, content_id)
    safe_id = str(piece.id)
    fmt = format.lower().strip()

    if fmt == "markdown":
        if piece.title:
            content_str = f"# {piece.title}\n\n{piece.body}"
        else:
            content_str = piece.body
        media_type = "text/markdown; charset=utf-8"
        filename = f"EventAI_{safe_id}.md"
    elif fmt == "text":
        if piece.title:
            content_str = f"{piece.title}\n\n{piece.body}"
        else:
            content_str = piece.body
        media_type = "text/plain; charset=utf-8"
        filename = f"EventAI_{safe_id}.txt"
    elif fmt == "json":
        data = ContentPublic.model_validate(piece).model_dump(mode="json")
        content_str = json.dumps(data, indent=2, ensure_ascii=False)
        media_type = "application/json"
        filename = f"EventAI_{safe_id}.json"
    else:
        raise http_error(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported format '{format}'. Supported formats: markdown, text, json.",
            "invalid_format",
        )

    return Response(
        content=content_str,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
