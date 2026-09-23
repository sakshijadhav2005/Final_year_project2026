"""Celery background tasks for asynchronous media processing and scheduled maintenance."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from app.workers.celery_app import celery_app

logger = structlog.get_logger("celery_tasks")


@celery_app.task(name="jobs.process_recording", bind=True)
def process_recording(
    self: Any,
    job_id: str,
    reuse_transcript: bool = False,
) -> dict[str, Any]:
    """Celery worker task executing the end-to-end processing pipeline for a job."""
    from app.services.job_runner import process_job

    logger.info("celery_process_recording_started", job_id=job_id)
    try:
        asyncio.run(process_job(job_id, reuse_transcript=reuse_transcript))
        logger.info("celery_process_recording_completed", job_id=job_id)
        return {"job_id": job_id, "status": "processed"}
    except Exception as exc:
        logger.error("celery_process_recording_failed", job_id=job_id, error=str(exc))
        err_msg = str(exc)
        try:
            from app.db.session import SessionLocal
            from app.models.job import Job

            async def _mark_failed(msg: str) -> None:
                async with SessionLocal() as db:
                    job = (
                        await db.execute(select(Job).where(Job.id == UUID(job_id)))
                    ).scalar_one_or_none()
                    if job and job.status not in (
                        "completed",
                        "failed",
                        "needs_reupload",
                        "cancelled",
                    ):
                        job.status = "failed"
                        job.error_code = "worker_error"
                        job.error_message = msg
                        job.finished_at = datetime.now(UTC)
                        await db.commit()

            asyncio.run(_mark_failed(err_msg))
        except Exception as db_exc:
            logger.error("celery_mark_job_failed_db_error", job_id=job_id, error=str(db_exc))

        raise exc


@celery_app.task(name="jobs.purge_expired_media")
def purge_expired_recordings() -> dict[str, Any]:
    """Automated retention cleanup task purging expired media files."""
    from app.services.job_runner import purge_expired_media

    logger.info("celery_purge_expired_recordings_started")
    try:
        purged = asyncio.run(purge_expired_media())
        logger.info("celery_purge_expired_recordings_completed", purged_count=purged)
        return {"purged_count": purged, "status": "completed"}
    except Exception as exc:
        logger.error("celery_purge_expired_recordings_failed", error=str(exc))
        raise exc
