from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eventai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend or settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "purge-expired-media-daily": {
        "task": "jobs.purge_expired_media",
        "schedule": crontab(hour=3, minute=0),
    },
}
