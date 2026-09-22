from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

from sqlalchemy.dialects.mysql.aiomysql import AsyncAdapt_aiomysql_connection

_orig_ping = AsyncAdapt_aiomysql_connection.ping
def _patched_ping(self, reconnect=True):
    return _orig_ping(self, reconnect)
AsyncAdapt_aiomysql_connection.ping = _patched_ping

settings = get_settings()

connect_args: dict = {}
engine_kwargs: dict = {"echo": settings.debug, "pool_pre_ping": not settings.is_sqlite}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}
    engine_kwargs["connect_args"] = connect_args
    if ":memory:" in settings.database_url:
        engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(settings.database_url, **engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.db.base import Base
    from app import models  # noqa: F401

    if settings.is_sqlite:
        from pathlib import Path

        Path(settings.media_root).mkdir(parents=True, exist_ok=True)
        db_path = settings.database_url.split("///")[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
