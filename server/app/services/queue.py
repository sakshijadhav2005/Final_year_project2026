from fastapi import BackgroundTasks

from app.core.config import get_settings


def enqueue_process_job(
    job_id: str,
    background_tasks: BackgroundTasks | None = None,
    *,
    reuse_transcript: bool = False,
) -> str:
    settings = get_settings()
    if settings.use_celery:
        try:
            from app.workers.tasks import process_recording

            process_recording.delay(job_id, reuse_transcript)
            return "celery"
        except Exception:
            pass
    from app.services.job_runner import process_job

    if background_tasks is None:
        raise RuntimeError("No queue available (Celery disabled and no BackgroundTasks)")
    background_tasks.add_task(process_job, job_id, reuse_transcript)
    return "inline"
