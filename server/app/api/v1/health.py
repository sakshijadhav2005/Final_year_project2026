from fastapi import APIRouter, status

from app import __version__
from app.core.config import get_settings
from app.schemas.common import HealthResponse, ReadyCheck, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        env=settings.eventai_env,
    )


@router.get("/ready", response_model=ReadyResponse, status_code=status.HTTP_200_OK)
async def ready() -> ReadyResponse:
    settings = get_settings()
    postgres_status = "unknown"
    redis_status = "unknown"

    try:
        from sqlalchemy import text

        from app.db.session import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        postgres_status = "ok"
    except Exception:
        postgres_status = "unavailable"

    try:
        from redis.asyncio import Redis

        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        await client.ping()
        await client.aclose()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"

    overall = "ok" if postgres_status == "ok" else "degraded"
    return ReadyResponse(
        status=overall,
        checks=ReadyCheck(postgres=postgres_status, redis=redis_status),
    )
