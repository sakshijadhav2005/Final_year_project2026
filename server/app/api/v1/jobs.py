import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_from_bearer_or_query
from app.core.exceptions import http_error
from app.core.security import UserRole
from app.db.session import SessionLocal, get_db
from app.models.job import Job, Transcript
from app.models.user import User
from app.schemas.common import JobPublic, RegenerRequest, TranscriptPublic
from app.services.guardrails import confidence_badge
from app.services.job_runner import TERMINAL
from app.services.queue import enqueue_process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _can_access(user: User, job: Job) -> bool:
    return user.role == UserRole.ADMIN or job.user_id == user.id


async def _load_job(db: AsyncSession, user: User, job_id: UUID) -> Job:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None or not _can_access(user, job):
        raise http_error(status.HTTP_404_NOT_FOUND, "Job not found", "not_found")
    return job


@router.get("", response_model=list[JobPublic])
async def list_jobs(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Job.user_id == user.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    return await _load_job(db, user, job_id)


@router.get("/{job_id}/transcript", response_model=TranscriptPublic | None)
async def get_transcript(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TranscriptPublic | None:
    await _load_job(db, user, job_id)
    row = (
        await db.execute(select(Transcript).where(Transcript.job_id == job_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    return TranscriptPublic(
        full_text=row.full_text,
        language=row.language,
        avg_confidence=row.avg_confidence,
        quality_json=row.quality_json,
        segments=row.segments,
        provider=row.provider,
        badge=confidence_badge(row.avg_confidence),
    )


@router.post("/{job_id}/cancel", response_model=JobPublic)
async def cancel_job(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    job = await _load_job(db, user, job_id)
    if job.status in TERMINAL:
        raise http_error(status.HTTP_409_CONFLICT, "Job already finished", "already_finished")
    job.status = "cancelled"
    job.error_code = "cancelled"
    job.error_message = "Cancelled by user"
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/regenerate", response_model=JobPublic, status_code=status.HTTP_202_ACCEPTED)
async def regenerate_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: RegenerRequest | None = None,
) -> Job:
    job = await _load_job(db, user, job_id)
    transcript = (
        await db.execute(select(Transcript).where(Transcript.job_id == job_id))
    ).scalar_one_or_none()
    if transcript is None:
        raise http_error(
            status.HTTP_400_BAD_REQUEST,
            "Transcript is not available to regenerate",
            "no_transcript",
        )
    payload = body or RegenerRequest()
    if payload.requested_types:
        job.requested_types = payload.requested_types
    if payload.target_languages:
        job.target_languages = payload.target_languages
    job.status = "queued"
    job.error_code = None
    job.error_message = None
    job.finished_at = None
    await db.commit()
    await db.refresh(job)
    enqueue_process_job(str(job.id), background_tasks, reuse_transcript=True)
    return job


@router.get("/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    user: Annotated[User, Depends(get_user_from_bearer_or_query)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    await _load_job(db, user, job_id)

    async def stream():
        while True:
            if await request.is_disconnected():
                break
            async with SessionLocal() as session:
                row = (
                    await session.execute(select(Job).where(Job.id == job_id))
                ).scalar_one_or_none()
            if row is None:
                break
            payload = {
                "id": str(row.id),
                "status": row.status,
                "progress": row.progress,
                "error_message": row.error_message,
            }
            yield f"event: job\ndata: {json.dumps(payload)}\n\n"
            if row.status in TERMINAL:
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    from sqlalchemy import delete

    from app.models.content import ContentPiece
    from app.models.job import AgentOutput, Transcript
    from app.models.recording import Recording

    job = await _load_job(db, user, job_id)
    await db.execute(delete(ContentPiece).where(ContentPiece.job_id == job_id))
    await db.execute(delete(Transcript).where(Transcript.job_id == job_id))
    await db.execute(delete(AgentOutput).where(AgentOutput.job_id == job_id))
    if job.recording_id is not None:
        await db.execute(delete(Recording).where(Recording.id == job.recording_id))
    await db.delete(job)
    await db.commit()
