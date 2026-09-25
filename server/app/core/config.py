from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
SERVER_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT / ".env"), str(SERVER_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "EventAI"
    eventai_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    secret_key: str = Field(default="change-me-in-production-use-long-random-string")
    access_token_expire_minutes: int = 10080
    refresh_token_expire_days: int = 30
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"

    database_url: str = f"sqlite+aiosqlite:///{(SERVER_DIR / 'data' / 'eventai.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    videodb_api_key: str = ""
    videodb_collection: str = ""
    stt_provider: str = "videodb"
    gemini_api_key: str = ""
    gemini_model_generate: str = "gemini-3.6-flash"
    gemini_model_analyze: str = "gemini-3.6-flash"
    portkey_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "gemini"

    rag_token_threshold: int = 12000
    rag_enabled: bool = True

    max_upload_mb: int = 500
    max_duration_sec: int = 10800
    media_retention_hours: int = 72
    clamav_enabled: bool = False
    media_root: str = str(SERVER_DIR / "data" / "media")

    # Cloud Storage (Cloudflare R2 / S3 / MinIO)
    storage_backend: Literal["local", "r2", "s3"] = "local"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "eventai-recordings"
    r2_public_domain: str = ""

    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "eventai-recordings"
    s3_region: str = "auto"

    sentry_dsn: str = ""
    bootstrap_admin_email: str = "admin@example.com"

    use_celery: bool = False
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 20
    eventai_fake_malware: bool = False

    @field_validator("database_url")
    @classmethod
    def resolve_sqlite_path(cls, value: str) -> str:
        if value.startswith("sqlite") and ":memory:" not in value:
            raw = value.split("///")[-1]
            path = Path(raw)
            if not path.is_absolute():
                path = (SERVER_DIR / path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{path.as_posix()}"
        return value

    @field_validator("secret_key")
    @classmethod
    def secret_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("SECRET_KEY must not be empty")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.eventai_env == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_mysql(self) -> bool:
        return self.database_url.startswith("mysql")

    @property
    def sync_database_url(self) -> str:
        return (
            self.database_url.replace("postgresql+asyncpg", "postgresql")
            .replace("mysql+aiomysql", "mysql+pymysql")
            .replace("sqlite+aiosqlite", "sqlite")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
