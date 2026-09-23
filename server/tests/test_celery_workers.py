from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.job import Job
from app.models.recording import Recording
from app.services.job_runner import process_job, purge_expired_media
from app.services.queue import enqueue_process_job
from app.workers.celery_app import celery_app
from app.workers.tasks import process_recording, purge_expired_recordings
from fastapi import BackgroundTasks
from sqlalchemy import select


# ---------------------------------------------------------------------------
# 1. Celery Application Initialization & Configuration
# ---------------------------------------------------------------------------
def test_celery_app_initialization() -> None:
    settings = get_settings()
    assert celery_app.main == "eventai"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert "app.workers.tasks" in celery_app.conf.include

    expected_backend = settings.celery_result_backend or settings.redis_url
    assert celery_app.conf.result_backend == expected_backend


def test_celery_task_registration() -> None:
    registered_tasks = celery_app.tasks
    assert "jobs.process_recording" in registered_tasks
    assert "jobs.purge_expired_media" in registered_tasks


def test_celery_beat_schedule() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "purge-expired-media-daily" in schedule
    entry = schedule["purge-expired-media-daily"]
    assert entry["task"] == "jobs.purge_expired_media"


# ---------------------------------------------------------------------------
# 2. Celery Worker Task Behavior & Signatures
# ---------------------------------------------------------------------------
def test_process_recording_task_signature_and_invocation() -> None:
    job_id = str(uuid.uuid4())

    with patch("app.services.job_runner.process_job", new_callable=AsyncMock) as mock_process:
        result = process_recording(job_id=job_id, reuse_transcript=True)

    assert result == {"job_id": job_id, "status": "processed"}
    mock_process.assert_awaited_once_with(job_id, reuse_transcript=True)


def test_process_recording_task_default_reuse_transcript() -> None:
    job_id = str(uuid.uuid4())

    with patch("app.services.job_runner.process_job", new_callable=AsyncMock) as mock_process:
        result = process_recording(job_id=job_id)

    assert result == {"job_id": job_id, "status": "processed"}
    mock_process.assert_awaited_once_with(job_id, reuse_transcript=False)


def test_purge_expired_recordings_task() -> None:
    with patch(
        "app.services.job_runner.purge_expired_media",
        new_callable=AsyncMock,
        return_value=5,
    ) as mock_purge:
        result = purge_expired_recordings()

    assert result == {"purged_count": 5, "status": "completed"}
    mock_purge.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. Queue Service Integration
# ---------------------------------------------------------------------------
def test_enqueue_process_job_with_celery_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "use_celery", True)
    job_id = str(uuid.uuid4())

    mock_task = MagicMock()
    mock_task.id = "mock-task-id-12345"

    with patch("app.workers.tasks.process_recording.delay", return_value=mock_task) as mock_delay:
        mode = enqueue_process_job(job_id, reuse_transcript=True)

    assert mode == "celery"
    mock_delay.assert_called_once_with(job_id, reuse_transcript=True)


def test_enqueue_process_job_with_celery_disabled_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "use_celery", False)
    job_id = str(uuid.uuid4())

    background_tasks = BackgroundTasks()
    mode = enqueue_process_job(job_id, background_tasks, reuse_transcript=False)

    assert mode == "inline"
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func == process_job
    assert task.args == (job_id, False)


def test_enqueue_process_job_celery_failure_with_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "use_celery", True)
    job_id = str(uuid.uuid4())

    background_tasks = BackgroundTasks()

    with patch(
        "app.workers.tasks.process_recording.delay",
        side_effect=ConnectionError("Redis connection refused"),
    ):
        mode = enqueue_process_job(job_id, background_tasks, reuse_transcript=False)

    assert mode == "inline"
    assert len(background_tasks.tasks) == 1


def test_enqueue_process_job_celery_failure_no_fallback_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "use_celery", True)
    job_id = str(uuid.uuid4())

    with patch(
        "app.workers.tasks.process_recording.delay",
        side_effect=ConnectionError("Redis connection refused"),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            enqueue_process_job(job_id, background_tasks=None)

    assert "Celery enqueue failed and no background_tasks fallback" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Worker Error & Missing Entity Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_process_job_missing_job_safe_return() -> None:
    # Random non-existent job ID should not crash or raise uncaught exception
    random_job_id = str(uuid.uuid4())
    await process_job(random_job_id)


@pytest.mark.asyncio
async def test_process_job_missing_recording_marks_failed() -> None:
    job_id = uuid.uuid4()
    missing_rec_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with SessionLocal() as db:
        job = Job(
            id=job_id,
            user_id=user_id,
            recording_id=missing_rec_id,
            status="queued",
            requested_types=["summary"],
            target_languages=["en"],
            progress={},
        )
        db.add(job)
        await db.commit()

    await process_job(str(job_id))

    async with SessionLocal() as db:
        updated = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert updated.status == "failed"
        assert updated.error_code == "missing_recording"
        assert "Recording missing" in (updated.error_message or "")


def test_process_recording_worker_exception_marks_job_failed() -> None:
    job_id = str(uuid.uuid4())

    with patch(
        "app.services.job_runner.process_job",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Unexpected unhandled worker panic"),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            process_recording(job_id=job_id)

    assert "Unexpected unhandled worker panic" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. Retention / Purge Active Job Protection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_purge_expired_media_protects_active_jobs(tmp_path: Path) -> None:
    rec_active_id = uuid.uuid4()
    rec_completed_id = uuid.uuid4()
    user_id = uuid.uuid4()

    media_active = tmp_path / "active_media.wav"
    media_active.write_bytes(b"active media content")

    media_completed = tmp_path / "completed_media.wav"
    media_completed.write_bytes(b"completed media content")

    # Both recordings are 100 hours old (beyond default 72 hours retention)
    old_time = datetime.now(UTC) - timedelta(hours=100)

    async with SessionLocal() as db:
        rec_active = Recording(
            id=rec_active_id,
            user_id=user_id,
            original_name="active.wav",
            storage_uri=str(media_active),
            content_type="audio/wav",
            size_bytes=100,
        )
        rec_completed = Recording(
            id=rec_completed_id,
            user_id=user_id,
            original_name="completed.wav",
            storage_uri=str(media_completed),
            content_type="audio/wav",
            size_bytes=100,
        )
        db.add_all([rec_active, rec_completed])
        await db.commit()

        # Update created_at to old_time
        rec_active.created_at = old_time
        rec_completed.created_at = old_time

        # Active job (transcribing)
        job_active = Job(
            id=uuid.uuid4(),
            user_id=user_id,
            recording_id=rec_active_id,
            status="transcribing",
            requested_types=["summary"],
            target_languages=["en"],
            progress={},
        )
        # Completed job (pending_review)
        job_completed = Job(
            id=uuid.uuid4(),
            user_id=user_id,
            recording_id=rec_completed_id,
            status="pending_review",
            requested_types=["summary"],
            target_languages=["en"],
            progress={},
        )
        db.add_all([job_active, job_completed])
        await db.commit()

    # Execute purge
    purged_count = await purge_expired_media()

    assert purged_count >= 1

    # Active recording MUST NOT be purged
    assert media_active.exists()

    async with SessionLocal() as db:
        rec_act = (
            await db.execute(select(Recording).where(Recording.id == rec_active_id))
        ).scalar_one()
        assert rec_act.storage_uri == str(media_active)

        # Completed recording's storage_uri was cleared
        rec_comp = (
            await db.execute(select(Recording).where(Recording.id == rec_completed_id))
        ).scalar_one()
        assert rec_comp.storage_uri == ""
