from collections.abc import AsyncGenerator

from sqlalchemy.dialects.mysql.aiomysql import AsyncAdapt_aiomysql_connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

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
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.db.base import Base

    if settings.is_sqlite:
        from pathlib import Path

        Path(settings.media_root).mkdir(parents=True, exist_ok=True)
        db_path = settings.database_url.split("///")[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_mysql:
            for table, col, col_type in [
                ("content_pieces", "event_id", "CHAR(32) NULL"),
                ("content_pieces", "user_id", "CHAR(32) NULL"),
                ("content_pieces", "author_name", "VARCHAR(255) NULL"),
                ("recordings", "event_id", "CHAR(32) NULL"),
                ("recordings", "storage_backend", "VARCHAR(32) NULL"),
                ("recordings", "sha256", "VARCHAR(64) NULL"),
            ]:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    )
                except Exception:
                    pass
        elif settings.is_sqlite:
            for table, col, col_type in [
                ("content_pieces", "event_id", "TEXT NULL"),
                ("content_pieces", "user_id", "TEXT NULL"),
                ("content_pieces", "author_name", "TEXT NULL"),
                ("recordings", "event_id", "TEXT NULL"),
                ("recordings", "storage_backend", "TEXT NULL"),
                ("recordings", "sha256", "TEXT NULL"),
            ]:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    )
                except Exception:
                    pass
