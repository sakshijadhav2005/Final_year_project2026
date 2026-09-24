import uuid
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.core.security import UserRole
from app.db.session import get_db
from app.models.event import Event
from app.models.job import Job
from app.models.recording import Recording
from app.models.user import User
from app.schemas.common import DEFAULT_CONTENT_TYPES, JobPublic
from app.services.queue import enqueue_process_job
from app.services.uploads import validate_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=JobPublic, status_code=status.HTTP_202_ACCEPTED)
async def create_upload(
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    consent_confirmed: bool = Form(False),
    retain_source: bool = Form(False),
    use_org_memory: bool = Form(False),
    requested_types: str = Form(",".join(DEFAULT_CONTENT_TYPES)),
    target_languages: str = Form("en"),
    event_id: str | None = Form(None),
) -> Job:
    if not consent_confirmed:
        raise http_error(
            status.HTTP_400_BAD_REQUEST,
            "Confirm that recorded participants were informed.",
            "consent_required",
        )

    validated_event_id: uuid.UUID | None = None
    if event_id is not None and event_id.strip():
        try:
            validated_event_id = uuid.UUID(event_id.strip())
        except ValueError as exc:
            raise http_error(
                status.HTTP_400_BAD_REQUEST,
                "Invalid event_id UUID format",
                "invalid_event_id",
            ) from exc

        event = (
            await db.execute(select(Event).where(Event.id == validated_event_id))
        ).scalar_one_or_none()
        if event is None:
            raise http_error(
                status.HTTP_404_NOT_FOUND,
                "Event not found",
                "event_not_found",
            )

        if user.role != UserRole.ADMIN and event.organizer_id != user.id:
            raise http_error(
                status.HTTP_403_FORBIDDEN,
                "You are not authorized to associate recordings with this event",
                "forbidden",
            )

    settings = get_settings()
    data = await file.read()
    filename = file.filename or "upload.bin"
    try:
        validate_upload(filename, file.content_type, len(data))
    except ValueError as exc:
        raise http_error(status.HTTP_400_BAD_REQUEST, str(exc), "invalid_file") from exc

    from app.services.storage import get_storage

    storage = get_storage()
    stored_name = f"{uuid4().hex}_{Path(filename).name}"
    storage_uri = storage.save_bytes(data, stored_name)

    recording = Recording(
        user_id=user.id,
        original_name=filename,
        storage_uri=storage_uri,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        consent_confirmed=True,
        retain_source=retain_source,
    )
    db.add(recording)
    await db.flush()

    types = [item.strip() for item in requested_types.split(",") if item.strip()]
    langs = [item.strip() for item in target_languages.split(",") if item.strip()]
    job = Job(
        user_id=user.id,
        recording_id=recording.id,
        event_id=validated_event_id,
        status="queued",
        requested_types=types or DEFAULT_CONTENT_TYPES,
        target_languages=langs or ["en"],
        use_org_memory=use_org_memory,
        progress={
            "quality_check": "queued",
            "topic_extraction": "queued",
            "highlight_detection": "queued",
            "speaker_analysis": "queued",
            "sentiment_analysis": "queued",
            "content_planner": "queued",
            "rag_retrieve": "queued",
            "generator": "queued",
            "guardrail": "queued",
            "translation": "queued",
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    enqueue_process_job(str(job.id), background_tasks)
    return job
