from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserProfilePublic(ORMModel):
    id: UUID | None = None
    user_id: UUID | None = None
    full_name: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    linkedin_handle: str | None = None
    instagram_handle: str | None = None
    website_url: str | None = None
    brand_tone: str | None = "authoritative_inspiring"
    custom_signoff: str | None = None


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=128)
    organization: str | None = Field(default=None, max_length=128)
    job_title: str | None = Field(default=None, max_length=128)
    bio: str | None = Field(default=None, max_length=2000)
    linkedin_handle: str | None = Field(default=None, max_length=64)
    instagram_handle: str | None = Field(default=None, max_length=64)
    website_url: str | None = Field(default=None, max_length=256)
    brand_tone: str | None = Field(default="authoritative_inspiring", max_length=64)
    custom_signoff: str | None = Field(default=None, max_length=256)


class UserPublic(ORMModel):
    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime | None = None
    profile: UserProfilePublic | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.EVENT_ORGANIZER
    full_name: str | None = None
    organization: str | None = None


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


class RolePatch(BaseModel):
    role: UserRole
