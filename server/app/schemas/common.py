from pydantic import BaseModel, ConfigDict

from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RolePatch,
    TokenResponse,
    UserProfilePublic,
    UserProfileUpdate,
    UserPublic,
)
from app.schemas.content import (
    DEFAULT_CONTENT_TYPES,
    ContentPatch,
    ContentPublic,
    CreatePostRequest,
    RejectRequest,
)
from app.schemas.jobs import (
    JobPublic,
    RegenerRequest,
    TranscriptPublic,
    UploadResponse,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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


__all__ = [
    "ContentPatch",
    "ContentPublic",
    "CreatePostRequest",
    "DEFAULT_CONTENT_TYPES",
    "HealthResponse",
    "JobPublic",
    "LoginRequest",
    "ORMModel",
    "ReadyCheck",
    "ReadyResponse",
    "RefreshRequest",
    "RegenerRequest",
    "RegisterRequest",
    "RejectRequest",
    "RolePatch",
    "TokenResponse",
    "TranscriptPublic",
    "UploadResponse",
    "UserPublic",
    "UserProfilePublic",
    "UserProfileUpdate",
]
