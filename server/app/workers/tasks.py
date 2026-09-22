import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(name="jobs.process_recording")
def process_recording(job_id: str) -> dict[str, str]:
    from app.services.job_runner import process_job

    asyncio.run(process_job(job_id))
    return {"job_id": job_id, "status": "processed"}
