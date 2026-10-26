from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.timing import RequestTimingMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(debug=settings.debug or not settings.is_production)
    from app.db.session import init_db

    await init_db()

    retention_task = None
    credentials_task = None
    if settings.validate_credentials_on_startup and settings.eventai_env != "test":
        import asyncio

        from app.services.credentials import validate_credentials

        # In the background: a slow network must not delay start-up.
        credentials_task = asyncio.create_task(validate_credentials())
    if not settings.use_celery and settings.eventai_env != "test":
        import asyncio

        from app.services.job_runner import purge_media_periodically, recover_interrupted_jobs

        await recover_interrupted_jobs()
        retention_task = asyncio.create_task(purge_media_periodically())
    yield
    for task in (retention_task, credentials_task):
        if task is not None:
            task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )
    application.add_middleware(RequestTimingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/health")
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    return application


app = create_app()
