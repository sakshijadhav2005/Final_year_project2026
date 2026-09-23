from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CONTENT_TYPES = ["summary", "blog", "linkedin", "newsletter", "ig_caption", "flyer"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ContentPublic(ORMModel):
    id: UUID
    job_id: UUID | None = None
    event_id: UUID | None = None
    user_id: UUID | None = None
    author_name: str | None = None
    type: str
    language: str
    title: str | None = None
    body: str
    structured: dict | None = None
    status: str
    version: int = 1
    grounding: dict | None = None
    moderation: dict | None = None
    created_at: datetime | None = None


class CreatePostRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    type: str = Field(default="user_post", max_length=32)
    event_id: UUID | None = None


class ContentPatch(BaseModel):
    title: str | None = None
    body: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
