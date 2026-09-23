from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobPublic(ORMModel):
    id: UUID
    status: str
    requested_types: list | None = None
    target_languages: list | None = None
    progress: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class UploadResponse(JobPublic):
    recording_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_backend: str
    storage_uri: str


class TranscriptPublic(BaseModel):
    full_text: str
    language: str
    avg_confidence: float | None
    quality_json: dict | None
    segments: list | None
    provider: str
    badge: str


class RegenerRequest(BaseModel):
    requested_types: list[str] | None = None
    target_languages: list[str] | None = None
