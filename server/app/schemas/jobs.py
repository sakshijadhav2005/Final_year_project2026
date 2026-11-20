from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobPublic(ORMModel):
    id: UUID
    user_id: UUID | None = None
    event_id: UUID | None = None
    status: str
    requested_types: list | None = None
    target_languages: list | None = None
    progress: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None
    # Human name for the session: its event's name, else the uploaded file's name.
    title: str | None = None


class TranscriptPublic(BaseModel):
    full_text: str
    language: str
    avg_confidence: float | None
    quality_json: dict | None
    segments: list | None
    provider: str
    badge: str
    edited: bool = False
    edited_at: datetime | None = None


class TranscriptUpdate(BaseModel):
    """A human correction of the transcript (names, jargon, [unclear audio] spans)."""

    full_text: str = Field(..., min_length=1, max_length=2_000_000)


class RegenerRequest(BaseModel):
    requested_types: list[str] | None = None
    target_languages: list[str] | None = None
