import asyncio
import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_from_bearer_or_query
from app.core.exceptions import http_error
from app.core.security import UserRole
from app.db.session import SessionLocal, get_db
from app.models.embedding import Embedding
from app.models.job import Job, Transcript
from app.models.recording import Recording
from app.models.user import User
from app.schemas.common import JobPublic, RegenerRequest, TranscriptPublic, TranscriptUpdate
from app.services.audit import write_audit
from app.services.guardrails import confidence_badge
from app.services.job_runner import TERMINAL
from app.services.queue import enqueue_process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _with_titles(db: AsyncSession, jobs: list[Job]) -> list[JobPublic]:
    """JobPublic rows with a readable title (event name, else the uploaded file name)."""
    from app.models.event import Event

    event_ids = {j.event_id for j in jobs if j.event_id}
    recording_ids = {j.recording_id for j in jobs if j.recording_id}
    events = (
        dict((await db.execute(select(Event.id, Event.name).where(Event.id.in_(event_ids)))).all())
        if event_ids
        else {}
    )
    files = (
        dict(
            (
                await db.execute(
                    select(Recording.id, Recording.original_name).where(Recording.id.in_(recording_ids))
                )
            ).all()
        )
        if recording_ids
        else {}
    )
    return [
        JobPublic.model_validate(j).model_copy(
            update={"title": events.get(j.event_id) or files.get(j.recording_id)}
        )
        for j in jobs
    ]


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
    scope: Annotated[
        str, Query(description="mine (default): your own sessions. all: every user's (admin only)")
    ] = "mine",
) -> list[JobPublic]:
    """Sessions of the signed-in user. Every role, admins included, sees only their
    own sessions here; an admin can ask for scope=all (the Admin page does)."""
    stmt = select(Job).order_by(Job.created_at.desc())
    if not (scope == "all" and user.role == UserRole.ADMIN):
        stmt = stmt.where(Job.user_id == user.id)
    result = await db.execute(stmt)
    return await _with_titles(db, list(result.scalars().all()))


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobPublic:
    job = await _load_job(db, user, job_id)
    return (await _with_titles(db, [job]))[0]


def _transcript_public(row: Transcript) -> TranscriptPublic:
    edit = (row.quality_json or {}).get("human_edit") or {}
    edited_at = None
    if edit.get("at"):
        try:
            edited_at = datetime.fromisoformat(edit["at"])
        except ValueError:
            edited_at = None
    return TranscriptPublic(
        full_text=row.full_text,
        language=row.language,
        avg_confidence=row.avg_confidence,
        quality_json=row.quality_json,
        segments=row.segments,
        provider=row.provider,
        badge=confidence_badge(row.avg_confidence),
        edited=bool(edit),
        edited_at=edited_at,
    )


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
    return _transcript_public(row)


@router.patch("/{job_id}/transcript", response_model=TranscriptPublic)
async def update_transcript(
    job_id: UUID,
    body: TranscriptUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TranscriptPublic:
    """Save a human correction of the transcript. Existing drafts are not changed:
    regenerate the session to write them again from the corrected text (the
    recording is not transcribed again). Not allowed while the pipeline is running."""
    job = await _load_job(db, user, job_id)
    if job.status not in TERMINAL:
        raise http_error(
            status.HTTP_409_CONFLICT,
            "The session is still processing; edit the transcript when it has finished",
            "job_running",
        )
    row = (
        await db.execute(select(Transcript).where(Transcript.job_id == job_id))
    ).scalar_one_or_none()
    if row is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "Transcript not found", "not_found")
    text = body.full_text.strip()
    if not text:
        raise http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Transcript cannot be empty", "empty")
    if text == row.full_text:
        return _transcript_public(row)

    previous_words = len(row.full_text.split())
    row.full_text = text
    # Segment timings are kept: the Sources panel re-aligns the edited words to the
    # recording, and spreads them evenly where it cannot.
    row.quality_json = {
        **(row.quality_json or {}),
        "human_edit": {
            "at": datetime.now(UTC).isoformat(),
            "by": str(user.id),
            "words_before": previous_words,
            "words_after": len(text.split()),
        },
    }
    # Old retrieval chunks describe the old text; the next run re-indexes on demand.
    await db.execute(
        delete(Embedding).where(
            Embedding.source_id == str(job_id), Embedding.source_type == "transcript_chunk"
        )
    )
    await write_audit(
        db,
        user_id=user.id,
        action="edit_transcript",
        resource_type="job",
        resource_id=str(job_id),
        detail=f"{previous_words} -> {len(text.split())} words",
    )
    await db.commit()
    await db.refresh(row)
    return _transcript_public(row)


@router.post("/{job_id}/cancel", response_model=JobPublic)
async def cancel_job(
    job_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Job:
    from app.services.job_runner import cancel_job_task

    cancel_job_task(str(job_id))
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
        # No transcript yet (e.g. the job was interrupted while transcribing):
        # re-run the whole pipeline from the stored recording if it still exists.
        recording = (
            await db.get(Recording, job.recording_id) if job.recording_id else None
        )
        if recording is None or not recording.storage_uri:
            raise http_error(
                status.HTTP_400_BAD_REQUEST,
                "Neither a transcript nor the original recording is available to regenerate",
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
    enqueue_process_job(
        str(job.id), background_tasks, reuse_transcript=transcript is not None
    )
    return job


@router.get("/{job_id}/media")
async def job_media(
    job_id: UUID,
    user: Annotated[User, Depends(get_user_from_bearer_or_query)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """The original recording, so the Content Studio can play the moment a sentence
    came from. Supports Range requests (seeking). Gone once the retention purge ran.
    Accepts ?token= because an <audio> element cannot send an Authorization header."""
    from pathlib import Path

    from app.services.storage import get_storage

    job = await _load_job(db, user, job_id)
    recording = (
        await db.execute(select(Recording).where(Recording.id == job.recording_id))
    ).scalar_one_or_none()
    content_type = (recording.content_type or "") if recording else ""
    if recording is None or not recording.storage_uri or not content_type.startswith(("audio/", "video/")):
        raise http_error(status.HTTP_404_NOT_FOUND, "Recording not available", "not_found")
    path = Path(get_storage().get_local_path(recording.storage_uri))
    if not path.is_file():
        raise http_error(status.HTTP_404_NOT_FOUND, "Recording not available", "not_found")
    return FileResponse(path, media_type=content_type)


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
    from app.models.content import ContentPiece
    from app.models.job import AgentOutput, Transcript
    from app.services.job_runner import cancel_job_task

    cancel_job_task(str(job_id))
    job = await _load_job(db, user, job_id)
    await db.execute(delete(ContentPiece).where(ContentPiece.job_id == job_id))
    await db.execute(delete(Transcript).where(Transcript.job_id == job_id))
    await db.execute(delete(AgentOutput).where(AgentOutput.job_id == job_id))
    if job.recording_id is not None:
        await db.execute(delete(Recording).where(Recording.id == job.recording_id))
    await db.delete(job)
    await db.commit()
