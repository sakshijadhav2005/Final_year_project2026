from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.db.session import get_db
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
    settings = get_settings()
    filename = file.filename or "upload.bin"
    
    # Pre-validate file extension and content type before downloading stream
    try:
        validate_upload(filename, file.content_type, 0)
    except ValueError as exc:
        raise http_error(status.HTTP_400_BAD_REQUEST, str(exc), "invalid_file") from exc

    from app.services.storage import get_storage
    import structlog

    storage = get_storage()
    stored_name = f"{uuid4().hex}_{Path(filename).name}"
    
    # Chunked streaming directly to disk/S3 (Does not consume RAM!)
    storage_uri, sha256_hash, total_bytes = storage.save_stream(file.file, stored_name)
    
    # Final validation for size limit
    try:
        validate_upload(filename, file.content_type, total_bytes)
    except ValueError as exc:
        storage.delete(storage_uri)
        raise http_error(status.HTTP_400_BAD_REQUEST, str(exc), "invalid_file") from exc

    logger = structlog.get_logger("uploads")
    logger.info("upload_integrity_verified", filename=filename, sha256=sha256_hash)

    from uuid import UUID
    ev_id = None
    if event_id:
        try:
            ev_id = UUID(event_id)
        except ValueError:
            raise http_error(status.HTTP_400_BAD_REQUEST, "Invalid event_id UUID", "invalid_id")

    recording = Recording(
        user_id=user.id,
        event_id=ev_id,
        original_name=filename,
        storage_uri=storage_uri,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=total_bytes,
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
