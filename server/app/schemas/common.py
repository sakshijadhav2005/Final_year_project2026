from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import UserRole

DEFAULT_CONTENT_TYPES = ["summary", "blog", "linkedin", "newsletter", "ig_caption", "flyer"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserPublic(ORMModel):
    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.EVENT_ORGANIZER


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    env: str


class ReadyCheck(BaseModel):
    postgres: str
    redis: str


class ReadyResponse(BaseModel):
    status: str
    checks: ReadyCheck


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


class TranscriptPublic(BaseModel):
    full_text: str
    language: str
    avg_confidence: float | None
    quality_json: dict | None
    segments: list | None
    provider: str
    badge: str


class ContentPublic(ORMModel):
    id: UUID
    job_id: UUID
    type: str
    language: str
    title: str | None
    body: str
    structured: dict | None
    status: str
    version: int
    grounding: dict | None = None
    moderation: dict | None = None


class ContentPatch(BaseModel):
    title: str | None = None
    body: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class RolePatch(BaseModel):
    role: UserRole


class RegenerRequest(BaseModel):
    requested_types: list[str] | None = None
    target_languages: list[str] | None = None
