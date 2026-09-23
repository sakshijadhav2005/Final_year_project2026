import structlog
from fastapi import BackgroundTasks

from app.core.config import get_settings

logger = structlog.get_logger("queue")


def enqueue_process_job(
    job_id: str,
    background_tasks: BackgroundTasks | None = None,
    *,
    reuse_transcript: bool = False,
) -> str:
    """Dispatches a job to the background processing queue.

    When Celery is enabled, sends the task to Redis broker for Celery workers.
    Falls back to FastAPI BackgroundTasks for local/test execution or if Celery fails.
    """
    settings = get_settings()
    if settings.use_celery:
        try:
            from app.workers.tasks import process_recording

            task = process_recording.delay(job_id, reuse_transcript=reuse_transcript)
            task_id = getattr(task, "id", None)
            logger.info("job_enqueued_to_celery", job_id=job_id, task_id=task_id)
            return "celery"
        except Exception as exc:
            logger.error("celery_enqueue_failed", job_id=job_id, error=str(exc))
            if background_tasks is None:
                raise RuntimeError(
                    f"Celery enqueue failed and no background_tasks fallback available: {exc}"
                ) from exc
            logger.warning("falling_back_to_background_tasks", job_id=job_id)

    from app.services.job_runner import process_job

    if background_tasks is None:
        raise RuntimeError("No queue available (Celery disabled and no BackgroundTasks)")

    background_tasks.add_task(process_job, job_id, reuse_transcript)
    return "inline"
