import asyncio

from app.workers.celery_app import celery_app


async def _run_with_fresh_engine(coro_factory):
    """Each Celery task runs in a brand-new event loop (asyncio.run).

    Pooled DB connections created by a previous loop cannot be reused, so we
    dispose the engine pool before and after running the coroutine.
    """
    from app.db.session import engine

    await engine.dispose()
    try:
        return await coro_factory()
    finally:
        await engine.dispose()


@celery_app.task(name="jobs.process_recording")
def process_recording(job_id: str, reuse_transcript: bool = False) -> dict[str, str]:
    from app.services.job_runner import process_job

    asyncio.run(_run_with_fresh_engine(lambda: process_job(job_id, reuse_transcript)))
    return {"job_id": job_id, "status": "processed"}


@celery_app.task(name="jobs.purge_expired_media")
def purge_expired_media() -> dict[str, int]:
    """Retention policy: delete raw media older than MEDIA_RETENTION_HOURS
    unless the organizer chose to retain the source file."""
    from app.services.job_runner import purge_expired_media as _purge

    purged = asyncio.run(_run_with_fresh_engine(_purge))
    return {"purged_count": purged}
