from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import get_settings

try:  # Optional MySQL support: work around aiomysql ping() signature mismatch.
    from sqlalchemy.dialects.mysql.aiomysql import AsyncAdapt_aiomysql_connection

    _orig_ping = AsyncAdapt_aiomysql_connection.ping

    def _patched_ping(self, reconnect=True):
        return _orig_ping(self, reconnect)

    AsyncAdapt_aiomysql_connection.ping = _patched_ping
except Exception:  # pragma: no cover - mysql driver not installed
    pass

settings = get_settings()

connect_args: dict = {}
engine_kwargs: dict = {"echo": settings.sql_echo, "pool_pre_ping": not settings.is_sqlite}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}
    engine_kwargs["connect_args"] = connect_args
    if ":memory:" in settings.database_url:
        engine_kwargs["poolclass"] = StaticPool
if settings.eventai_env == "test" and "poolclass" not in engine_kwargs:
    # Each TestClient runs its own event loop; pooled async connections
    # cannot be shared across loops, so don't pool in tests.
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.database_url, **engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
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
        await _upgrade_columns(conn)


# Columns added after the first release. create_all() does not alter existing
# tables, so add them in place (each statement is idempotent / failure-tolerant).
_UPGRADE_COLUMNS: list[tuple[str, str, dict[str, str]]] = [
    ("content_pieces", "event_id", {"postgresql": "UUID", "sqlite": "CHAR(32)", "mysql": "CHAR(32)"}),
    ("content_pieces", "user_id", {"postgresql": "UUID", "sqlite": "CHAR(32)", "mysql": "CHAR(32)"}),
    ("content_pieces", "author_name", {"postgresql": "VARCHAR(255)", "sqlite": "VARCHAR(255)", "mysql": "VARCHAR(255)"}),
    ("recordings", "event_id", {"postgresql": "UUID", "sqlite": "CHAR(32)", "mysql": "CHAR(32)"}),
    ("events", "location", {"postgresql": "VARCHAR(255)", "sqlite": "VARCHAR(255)", "mysql": "VARCHAR(255)"}),
    ("events", "banner_image", {"postgresql": "VARCHAR(1024)", "sqlite": "VARCHAR(1024)", "mysql": "VARCHAR(1024)"}),
    ("events", "description", {"postgresql": "TEXT", "sqlite": "TEXT", "mysql": "TEXT"}),
    ("jobs", "event_id", {"postgresql": "UUID", "sqlite": "CHAR(32)", "mysql": "CHAR(32)"}),
]


async def _upgrade_columns(conn) -> None:
    from sqlalchemy import inspect, text

    dialect = conn.dialect.name

    def _existing(sync_conn) -> dict[str, set[str]]:
        insp = inspect(sync_conn)
        return {
            table: {col["name"] for col in insp.get_columns(table)}
            for table in {t for t, _, _ in _UPGRADE_COLUMNS}
            if insp.has_table(table)
        }

    existing = await conn.run_sync(_existing)
    for table, column, types in _UPGRADE_COLUMNS:
        if table in existing and column not in existing[table] and dialect in types:
            await conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {column} {types[dialect]} NULL")
            )

    # Backfill jobs.event_id from the uploaded recording for jobs created before
    # the column existed.
    if dialect == "postgresql":
        await conn.execute(
            text(
                "UPDATE jobs SET event_id = r.event_id FROM recordings r "
                "WHERE jobs.recording_id = r.id AND jobs.event_id IS NULL "
                "AND r.event_id IS NOT NULL"
            )
        )
    else:
        await conn.execute(
            text(
                "UPDATE jobs SET event_id = (SELECT r.event_id FROM recordings r "
                "WHERE r.id = jobs.recording_id) WHERE event_id IS NULL"
            )
        )
