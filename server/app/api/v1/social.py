"""Connect social media accounts and publish approved content to them.

Flow (LinkedIn):
1. ``GET /social/linkedin/connect`` (signed in) returns the LinkedIn sign-in URL and sets a
   short-lived nonce cookie. The browser goes to LinkedIn.
2. LinkedIn redirects to ``GET /social/linkedin/callback?code&state``. ``state`` is a signed
   token naming the EventAI user plus the nonce; the nonce must match the cookie, so a
   link crafted by someone else cannot attach their LinkedIn account to this user.
3. ``POST /content/{id}/publish`` posts an *approved* draft to the connected account.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.content import PUBLIC_STATUSES, _load_piece
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.core.security import create_token, decode_token
from app.db.session import get_db
from app.models.social import SocialAccount, SocialPost
from app.models.user import User
from app.services.audit import write_audit
from app.services.publishers import PublishError, linkedin
from app.services.publishers.tokens import decrypt_token, encrypt_token

router = APIRouter(tags=["social"])

STATE_COOKIE = "eventai_oauth_nonce"
STATE_TTL = timedelta(minutes=10)
Platform = Literal["linkedin"]

# Not 401 for "reconnect": the web app treats 401 as its own session expiring.
_PUBLISH_ERROR_STATUS = {
    "too_long": status.HTTP_400_BAD_REQUEST,
    "empty_post": status.HTTP_400_BAD_REQUEST,
    "reconnect_required": status.HTTP_409_CONFLICT,
    "permission_denied": status.HTTP_409_CONFLICT,
    "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
}


class SocialAccountPublic(BaseModel):
    platform: str
    display_name: str | None
    connected_at: datetime | None
    expires_at: datetime | None
    expired: bool


class PlatformStatus(BaseModel):
    platform: str
    configured: bool  # the server has app credentials for this platform
    account: SocialAccountPublic | None


class ConnectResponse(BaseModel):
    authorize_url: str


class PublishRequest(BaseModel):
    platform: Platform = "linkedin"


class SocialPostPublic(BaseModel):
    id: UUID
    content_id: UUID
    platform: str
    status: str
    external_post_id: str | None
    post_url: str | None
    error: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


def _aware(value: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; everything is stored in UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _is_expired(account: SocialAccount) -> bool:
    expires = _aware(account.expires_at)
    return expires is not None and expires <= datetime.now(UTC)


def _account_public(account: SocialAccount) -> SocialAccountPublic:
    return SocialAccountPublic(
        platform=account.platform,
        display_name=account.display_name,
        connected_at=account.updated_at,
        expires_at=account.expires_at,
        expired=_is_expired(account) and not account.refresh_token_enc,
    )


async def _get_account(db: AsyncSession, user_id: UUID, platform: str) -> SocialAccount | None:
    return (
        await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id, SocialAccount.platform == platform
            )
        )
    ).scalar_one_or_none()


def _settings_redirect(platform: str, outcome: str, reason: str | None = None) -> RedirectResponse:
    params = {"social": platform, "status": outcome}
    if reason:
        params["reason"] = reason
    url = f"{get_settings().frontend_url.rstrip('/')}/settings?{urlencode(params)}"
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(STATE_COOKIE, path="/api/v1/social")
    return response


@router.get("/social/accounts", response_model=list[PlatformStatus])
async def list_accounts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PlatformStatus]:
    accounts = {
        a.platform: a
        for a in (
            await db.execute(select(SocialAccount).where(SocialAccount.user_id == user.id))
        ).scalars()
    }
    return [
        PlatformStatus(
            platform="linkedin",
            configured=linkedin.is_configured(),
            account=_account_public(accounts["linkedin"]) if "linkedin" in accounts else None,
        )
    ]


@router.get("/social/linkedin/connect", response_model=ConnectResponse)
async def linkedin_connect(
    response: Response, user: Annotated[User, Depends(get_current_user)]
) -> ConnectResponse:
    if not linkedin.is_configured():
        raise http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "LinkedIn is not set up on this server (LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET).",
            "not_configured",
        )
    nonce = secrets.token_urlsafe(24)
    state = create_token(
        subject=str(user.id),
        token_type="oauth_state",
        expires_delta=STATE_TTL,
        extra={"platform": "linkedin", "nonce": nonce},
    )
    response.set_cookie(
        STATE_COOKIE,
        nonce,
        max_age=int(STATE_TTL.total_seconds()),
        httponly=True,
        samesite="lax",  # sent on the top-level redirect back from LinkedIn
        secure=get_settings().is_production,
        path="/api/v1/social",
    )
    return ConnectResponse(authorize_url=linkedin.authorize_url(state))


@router.get("/social/linkedin/callback", include_in_schema=False)
async def linkedin_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:  # the user pressed Cancel on LinkedIn, or the app lacks a product
        return _settings_redirect("linkedin", "error", error)
    payload = decode_token(state or "")
    if (
        not code
        or not payload
        or payload.get("type") != "oauth_state"
        or payload.get("platform") != "linkedin"
    ):
        return _settings_redirect("linkedin", "error", "invalid_state")
    cookie = request.cookies.get(STATE_COOKIE)
    if not cookie or not secrets.compare_digest(cookie, str(payload.get("nonce", ""))):
        return _settings_redirect("linkedin", "error", "invalid_state")
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        return _settings_redirect("linkedin", "error", "invalid_state")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        return _settings_redirect("linkedin", "error", "invalid_state")

    try:
        tokens = await linkedin.exchange_code(code)
        member_id, name = await linkedin.fetch_member(tokens.access_token)
    except PublishError as exc:
        return _settings_redirect("linkedin", "error", exc.code)

    account = await _get_account(db, user.id, "linkedin")
    if account is None:
        account = SocialAccount(user_id=user.id, platform="linkedin")
        db.add(account)
    account.external_id = member_id
    account.display_name = name
    account.access_token_enc = encrypt_token(tokens.access_token)
    account.refresh_token_enc = encrypt_token(tokens.refresh_token) if tokens.refresh_token else None
    account.expires_at = (
        datetime.now(UTC) + timedelta(seconds=tokens.expires_in) if tokens.expires_in else None
    )
    account.scopes = tokens.scope
    await write_audit(
        db, user_id=user.id, action="social_connect", resource_type="social_account",
        resource_id="linkedin",
    )
    await db.commit()
    return _settings_redirect("linkedin", "connected")


@router.delete("/social/accounts/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    platform: Platform,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    account = await _get_account(db, user.id, platform)
    if account is not None:
        await db.delete(account)
        await write_audit(
            db, user_id=user.id, action="social_disconnect", resource_type="social_account",
            resource_id=platform,
        )
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _linkedin_access_token(db: AsyncSession, account: SocialAccount) -> str:
    token = decrypt_token(account.access_token_enc)
    if token is None:
        raise PublishError(
            "Your LinkedIn connection is no longer valid. Reconnect LinkedIn in Settings.",
            "reconnect_required",
        )
    if not _is_expired(account):
        return token
    refresh_token = decrypt_token(account.refresh_token_enc) if account.refresh_token_enc else None
    if not refresh_token:
        raise PublishError(
            "Your LinkedIn connection expired. Reconnect LinkedIn in Settings.", "reconnect_required"
        )
    fresh = await linkedin.refresh(refresh_token)
    account.access_token_enc = encrypt_token(fresh.access_token)
    if fresh.refresh_token:
        account.refresh_token_enc = encrypt_token(fresh.refresh_token)
    account.expires_at = (
        datetime.now(UTC) + timedelta(seconds=fresh.expires_in) if fresh.expires_in else None
    )
    return fresh.access_token


@router.post("/content/{content_id}/publish", response_model=SocialPostPublic)
async def publish_content(
    content_id: UUID,
    body: PublishRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocialPost:
    piece = await _load_piece(db, user, content_id, write=True)
    if piece.status not in PUBLIC_STATUSES:
        raise http_error(
            status.HTTP_409_CONFLICT, "Approve this draft before publishing it.", "not_approved"
        )
    already = (
        await db.execute(
            select(SocialPost).where(
                SocialPost.content_id == piece.id,
                SocialPost.platform == body.platform,
                SocialPost.status == "posted",
            )
        )
    ).scalar_one_or_none()
    if already is not None:
        raise http_error(
            status.HTTP_409_CONFLICT, "This draft is already published there.", "already_published"
        )
    account = await _get_account(db, user.id, body.platform)
    if account is None:
        raise http_error(
            status.HTTP_400_BAD_REQUEST,
            "Connect your LinkedIn account in Settings first.",
            "not_connected",
        )

    post = SocialPost(content_id=piece.id, user_id=user.id, platform=body.platform)
    try:
        token = await _linkedin_access_token(db, account)
        text = linkedin.build_post_text(piece.title, piece.body or "")
        result = await linkedin.publish(token, account.external_id, text)
    except PublishError as exc:
        post.status = "failed"
        post.error = str(exc)
        db.add(post)
        await write_audit(
            db, user_id=user.id, action="publish_failed", resource_type="content",
            resource_id=str(piece.id), detail=f"{body.platform}: {exc.code}",
        )
        await db.commit()
        raise http_error(_PUBLISH_ERROR_STATUS.get(exc.code, 502), str(exc), exc.code) from exc

    post.status = "posted"
    post.external_post_id = result.external_post_id
    post.post_url = result.post_url
    db.add(post)
    await write_audit(
        db, user_id=user.id, action="publish", resource_type="content",
        resource_id=str(piece.id), detail=f"{body.platform}: {result.external_post_id}",
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.get("/content/{content_id}/publications", response_model=list[SocialPostPublic])
async def list_publications(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SocialPost]:
    piece = await _load_piece(db, user, content_id, write=True)
    rows = await db.execute(
        select(SocialPost)
        .where(SocialPost.content_id == piece.id)
        .order_by(SocialPost.created_at.desc())
    )
    return list(rows.scalars().all())
