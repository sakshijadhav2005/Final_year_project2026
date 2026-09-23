import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.db.session import get_db
from app.models.job import Job
from app.models.recording import Recording
from app.models.user import User
from app.schemas.common import DEFAULT_CONTENT_TYPES, UploadResponse
from app.services.queue import enqueue_process_job
from app.services.storage import get_storage
from app.services.uploads import validate_upload_metadata

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
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
) -> UploadResponse:
    if not consent_confirmed:
        raise http_error(
            status.HTTP_400_BAD_REQUEST,
            "Confirm that recorded participants were informed.",
            "consent_required",
        )

    raw_filename = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"

    # Pre-stream metadata validation (whitelisted extensions, MIME prefix)
    try:
        sanitized_filename = validate_upload_metadata(raw_filename, content_type)
    except ValueError as exc:
        raise http_error(status.HTTP_400_BAD_REQUEST, str(exc), "invalid_file") from exc

    # Parse and validate event_id if supplied
    parsed_event_id: uuid.UUID | None = None
    if event_id:
        try:
            parsed_event_id = uuid.UUID(event_id)
        except ValueError as exc:
            raise http_error(
                status.HTTP_400_BAD_REQUEST, "Invalid event_id format", "invalid_event_id"
            ) from exc

    settings = get_settings()
    recording_id = uuid.uuid4()
    storage = get_storage()

    destination_key = storage.generate_key(
        user_id=user.id,
        recording_id=recording_id,
        filename=sanitized_filename,
        event_id=parsed_event_id,
    )

    # Stream upload in chunks, compute SHA-256 and enforce size limits without OOM
    try:
        upload_result = await storage.stream_upload(
            file=file,
            destination_key=destination_key,
            max_bytes=settings.max_upload_bytes,
            chunk_size=settings.upload_chunk_size,
            content_type=content_type,
        )
    except ValueError as exc:
        # Client validation errors (e.g. empty file, exceeds max size)
        raise http_error(status.HTTP_400_BAD_REQUEST, str(exc), "invalid_file") from exc
    except Exception as exc:
        raise http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Failed to store media upload: {exc}",
            "storage_error",
        ) from exc

    recording = Recording(
        id=recording_id,
        user_id=user.id,
        event_id=parsed_event_id,
        original_name=raw_filename,
        storage_uri=upload_result.storage_uri,
        storage_backend=upload_result.storage_backend,
        sha256=upload_result.sha256,
        content_type=content_type,
        size_bytes=upload_result.size_bytes,
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

    return UploadResponse(
        id=job.id,
        status=job.status,
        requested_types=job.requested_types,
        target_languages=job.target_languages,
        progress=job.progress,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        finished_at=job.finished_at,
        recording_id=recording.id,
        filename=sanitized_filename,
        content_type=recording.content_type,
        size_bytes=recording.size_bytes,
        sha256=upload_result.sha256,
        storage_backend=upload_result.storage_backend,
        storage_uri=recording.storage_uri,
    )
