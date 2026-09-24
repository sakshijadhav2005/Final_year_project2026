import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(name="jobs.process_recording")
def process_recording(job_id: str) -> dict[str, str]:
    from app.services.job_runner import process_job

    asyncio.run(process_job(job_id))
    return {"job_id": job_id, "status": "processed"}


@celery_app.task(name="jobs.purge_expired_media")
def purge_expired_media() -> dict[str, int]:
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.db.session import async_session_maker
    from app.models.recording import Recording
    from app.services.storage import get_storage
    import structlog

    logger = structlog.get_logger("retention")

    async def _purge():
        # GDPR: Delete raw video files older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        purged = 0
        
        async with async_session_maker() as db:
            # Find old recordings that haven't been purged yet
            result = await db.execute(
                select(Recording).where(
                    Recording.created_at < cutoff, 
                    Recording.storage_uri != "purged_due_to_retention_policy"
                )
            )
            recordings = result.scalars().all()
            storage = get_storage()
            
            for rec in recordings:
                if rec.retain_source:
                    continue  # Organizer paid for permanent storage
                
                try:
                    if storage.delete(rec.storage_uri):
                        rec.storage_uri = "purged_due_to_retention_policy"
                        purged += 1
                except Exception as exc:
                    logger.error("purge_failed", recording_id=str(rec.id), error=str(exc))
            
            if purged > 0:
                await db.commit()
                
        logger.info("retention_purge_complete", count=purged)
        return {"purged_count": purged}

    return asyncio.run(_purge())
