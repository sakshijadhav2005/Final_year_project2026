import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import http_error
from app.core.security import (
    UserRole,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.common import TokenResponse, UserPublic
from fastapi import status


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_public(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


async def register_user(db: AsyncSession, email: str, password: str, role: UserRole) -> TokenResponse:
    settings = get_settings()
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise http_error(status.HTTP_409_CONFLICT, "Email already registered", "email_taken")

    assigned = role
    if assigned == UserRole.ADMIN and email.lower() != settings.bootstrap_admin_email.lower():
        assigned = UserRole.EVENT_ORGANIZER
    if email.lower() == settings.bootstrap_admin_email.lower():
        assigned = UserRole.ADMIN

    hashed = await asyncio.to_thread(hash_password, password)
    user = User(
        email=email.lower(),
        hashed_password=hashed,
        role=assigned,
    )
    db.add(user)
    await db.flush()
    return await issue_tokens(db, user)


async def login_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "Invalid email or password", "invalid_credentials")
    
    is_valid = await asyncio.to_thread(verify_password, password, user.hashed_password)
    if not is_valid:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "Invalid email or password", "invalid_credentials")
    if not user.is_active:
        raise http_error(status.HTTP_403_FORBIDDEN, "Account disabled", "disabled")
    return await issue_tokens(db, user)


async def issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    settings = get_settings()
    access = create_access_token(str(user.id), UserRole(user.role))
    refresh = create_refresh_token(str(user.id))
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=access, refresh_token=refresh, user=_to_public(user))


async def rotate_refresh(db: AsyncSession, refresh_token: str) -> TokenResponse:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise http_error(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token", "invalid_refresh")
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "Refresh token expired", "invalid_refresh")
    expires_at = row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
    if expires_at < datetime.now(UTC):
        raise http_error(status.HTTP_401_UNAUTHORIZED, "Refresh token expired", "invalid_refresh")
    row.revoked = True
    user = (await db.execute(select(User).where(User.id == UUID(payload["sub"])))).scalar_one_or_none()
    if user is None:
        raise http_error(status.HTTP_401_UNAUTHORIZED, "User not found", "invalid_refresh")
    return await issue_tokens(db, user)


async def revoke_refresh(db: AsyncSession, refresh_token: str) -> None:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()
    if row:
        row.revoked = True
        await db.commit()
