"""Connect social media accounts and publish (or schedule) approved content to them.

Flow (same for every platform):
1. ``GET /social/{platform}/connect`` (signed in) returns the platform's sign-in URL and
   sets a short-lived cookie with a nonce (and the PKCE verifier X needs).
2. The platform redirects to ``GET /social/{platform}/callback?code&state``. ``state`` is a
   signed token naming the EventAI user plus the nonce; the nonce must match the cookie, so
   a link crafted by someone else cannot attach their account to this user.
3. ``POST /content/{id}/publish`` posts an *approved* draft now, or at ``scheduled_for``.
   Instagram needs an image: a recap card is rendered from the flyer copy, or the user
   uploads one with ``POST /content/{id}/publish/instagram``.

The rules themselves live in :mod:`app.services.social_publishing`.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.content import _load_piece
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.core.security import create_token, decode_token
from app.db.session import get_db
from app.models.content import ContentPiece
from app.models.job import Job
from app.models.social import SocialAccount, SocialPost
from app.models.user import User
from app.services import social_publishing as sp
from app.services.audit import write_audit
from app.services.publishers import SUPPORTED_PLATFORMS, PublishError, images
from app.services.publishers.text import plain_text
from app.services.publishers.tokens import encrypt_token

router = APIRouter(tags=["social"])

STATE_COOKIE = "eventai_oauth_nonce"
STATE_TTL = timedelta(minutes=10)
Platform = Literal["linkedin", "instagram", "facebook", "x"]

# Not 401 for "reconnect": the web app treats 401 as its own session expiring.
_ERROR_STATUS = {
    "too_long": status.HTTP_400_BAD_REQUEST,
    "empty_post": status.HTTP_400_BAD_REQUEST,
    "invalid_image": status.HTTP_400_BAD_REQUEST,
    "image_too_large": status.HTTP_400_BAD_REQUEST,
    "invalid_schedule": status.HTTP_400_BAD_REQUEST,
    "wrong_type": status.HTTP_400_BAD_REQUEST,
    "not_connected": status.HTTP_400_BAD_REQUEST,
    "not_approved": status.HTTP_409_CONFLICT,
    "already_published": status.HTTP_409_CONFLICT,
    "not_scheduled": status.HTTP_409_CONFLICT,
    "reconnect_required": status.HTTP_409_CONFLICT,
    "permission_denied": status.HTTP_409_CONFLICT,
    "not_public": status.HTTP_503_SERVICE_UNAVAILABLE,
    "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
}


def _http(exc: PublishError):
    return http_error(_ERROR_STATUS.get(exc.code, status.HTTP_502_BAD_GATEWAY), str(exc), exc.code)


class SocialAccountPublic(BaseModel):
    platform: str
    display_name: str | None
    connected_at: datetime | None
    expires_at: datetime | None
    expired: bool


class PlatformStatus(BaseModel):
    platform: str
    label: str
    configured: bool  # the server has app credentials for this platform
    accepts: list[str]  # draft kinds this platform publishes
    account: SocialAccountPublic | None


class ConnectResponse(BaseModel):
    authorize_url: str


class PublishRequest(BaseModel):
    platform: Platform = "linkedin"
    scheduled_for: datetime | None = None  # omit to publish now


class SocialPostPublic(BaseModel):
    id: UUID
    content_id: UUID
    platform: str
    status: str
    external_post_id: str | None
    post_url: str | None
    error: str | None
    scheduled_for: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class DraftPlatformState(BaseModel):
    status: str  # not_published | scheduled | pending | posted | failed | cancelled
    post_url: str | None = None
    scheduled_for: datetime | None = None


class PublishableDraft(BaseModel):
    content_id: UUID
    kind: str
    platforms: dict[str, DraftPlatformState]  # every platform this draft can go to
    title: str | None
    language: str
    excerpt: str
    job_id: UUID | None
    created_at: datetime | None


class PublishPreview(BaseModel):
    platform: str
    text: str
    characters: int
    limit: int
    problems: list[str]
    image_preview_path: str | None  # Instagram: GET this (signed in) for the recap card


def _account_public(account: SocialAccount) -> SocialAccountPublic:
    return SocialAccountPublic(
        platform=account.platform,
        display_name=account.display_name,
        connected_at=account.updated_at,
        expires_at=account.expires_at,
        expired=not sp.connection_usable(account),
    )


def _settings_redirect(platform: str, outcome: str, reason: str | None = None) -> RedirectResponse:
    params = {"social": platform, "status": outcome}
    if reason:
        params["reason"] = reason
    url = f"{get_settings().frontend_url.rstrip('/')}/settings?{urlencode(params)}"
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(STATE_COOKIE, path="/api/v1/social")
    return response


# ── Accounts ───────────────────────────────────────────────────────────────────


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
            platform=name,
            label=sp.PLATFORMS[name].LABEL,
            configured=sp.PLATFORMS[name].is_configured(),
            accepts=sorted(sp.PLATFORMS[name].ACCEPTS),
            account=_account_public(accounts[name]) if name in accounts else None,
        )
        for name in SUPPORTED_PLATFORMS
    ]


@router.get("/social/{platform}/connect", response_model=ConnectResponse)
async def connect(
    platform: Platform, response: Response, user: Annotated[User, Depends(get_current_user)]
) -> ConnectResponse:
    module = sp.PLATFORMS[platform]
    if not module.is_configured():
        raise http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{module.LABEL} is not set up on this server ({module.ENV_HINT}).",
            "not_configured",
        )
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)  # PKCE (X); unused by the other platforms
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = create_token(
        subject=str(user.id),
        token_type="oauth_state",
        expires_delta=STATE_TTL,
        extra={"platform": platform, "nonce": nonce},
    )
    response.set_cookie(
        STATE_COOKIE,
        f"{nonce}:{verifier}",
        max_age=int(STATE_TTL.total_seconds()),
        httponly=True,
        samesite="lax",  # sent on the top-level redirect back from the platform
        secure=get_settings().is_production,
        path="/api/v1/social",
    )
    return ConnectResponse(authorize_url=module.authorize_url(state, challenge))


@router.get("/social/{platform}/callback", include_in_schema=False)
async def callback(
    platform: Platform,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_reason: str | None = None,
) -> RedirectResponse:
    if error:  # the user pressed Cancel, or the app lacks a product / permission
        return _settings_redirect(platform, "error", error_reason or error)
    payload = decode_token(state or "")
    if (
        not code
        or not payload
        or payload.get("type") != "oauth_state"
        or payload.get("platform") != platform
    ):
        return _settings_redirect(platform, "error", "invalid_state")
    nonce, _, verifier = (request.cookies.get(STATE_COOKIE) or "").partition(":")
    if not nonce or not secrets.compare_digest(nonce, str(payload.get("nonce", ""))):
        return _settings_redirect(platform, "error", "invalid_state")
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        return _settings_redirect(platform, "error", "invalid_state")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        return _settings_redirect(platform, "error", "invalid_state")

    module = sp.PLATFORMS[platform]
    try:
        tokens = await module.exchange_code(code, verifier)
        identity = await module.fetch_identity(tokens.access_token)
    except PublishError as exc:
        return _settings_redirect(platform, "error", exc.code)

    account = await sp.get_account(db, user.id, platform)
    if account is None:
        account = SocialAccount(user_id=user.id, platform=platform)
        db.add(account)
    account.external_id = identity.external_id
    account.display_name = identity.display_name
    if identity.access_token:  # Facebook: the Page's own token, which does not expire
        account.access_token_enc = encrypt_token(identity.access_token)
        account.refresh_token_enc = None
        account.expires_at = None
    else:
        account.access_token_enc = encrypt_token(tokens.access_token)
        account.refresh_token_enc = encrypt_token(tokens.refresh_token) if tokens.refresh_token else None
        account.expires_at = (
            datetime.now(UTC) + timedelta(seconds=tokens.expires_in) if tokens.expires_in else None
        )
    account.scopes = tokens.scope
    await write_audit(
        db, user_id=user.id, action="social_connect", resource_type="social_account",
        resource_id=platform,
    )
    await db.commit()
    return _settings_redirect(platform, "connected")


@router.delete("/social/accounts/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    platform: Platform,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    account = await sp.get_account(db, user.id, platform)
    if account is not None:
        await db.delete(account)
        await write_audit(
            db, user_id=user.id, action="social_disconnect", resource_type="social_account",
            resource_id=platform,
        )
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Instagram images ───────────────────────────────────────────────────────────


@router.get("/content/{content_id}/social-image")
async def preview_social_image(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """The recap card that "Publish to Instagram" uses when no image is uploaded."""
    piece = await _load_piece(db, user, content_id, write=True)
    data = images.render_card(await sp.card_for(db, piece))
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/social/media/{token}", include_in_schema=False)
async def public_social_image(token: str, db: Annotated[AsyncSession, Depends(get_db)]) -> Response:
    """Signed, expiring link that Instagram's servers download the post image from."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "social_media":
        raise http_error(status.HTTP_404_NOT_FOUND, "Not found", "not_found")
    try:
        post_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        raise http_error(status.HTTP_404_NOT_FOUND, "Not found", "not_found") from None
    post = (await db.execute(select(SocialPost).where(SocialPost.id == post_id))).scalar_one_or_none()
    if post is None or not post.image_uri or post.image_uri.startswith("s3://"):
        raise http_error(status.HTTP_404_NOT_FOUND, "Not found", "not_found")
    path = Path(post.image_uri)
    if not path.is_file():
        raise http_error(status.HTTP_404_NOT_FOUND, "Not found", "not_found")
    return FileResponse(path, media_type="image/jpeg")


# ── Publishing ─────────────────────────────────────────────────────────────────


async def _publish(
    db: AsyncSession,
    user: User,
    content_id: UUID,
    platform: str,
    *,
    upload: bytes | None = None,
    scheduled_for: datetime | None = None,
) -> SocialPost:
    piece = await _load_piece(db, user, content_id, write=True)
    try:
        post, account = await sp.prepare(
            db, user.id, piece, platform, upload=upload, scheduled_for=scheduled_for
        )
        if post.status == "scheduled":
            await db.refresh(post)
            return post
        return await sp.send(db, post, piece, account)
    except PublishError as exc:
        raise _http(exc) from exc


@router.post("/content/{content_id}/publish", response_model=SocialPostPublic)
async def publish_content(
    content_id: UUID,
    body: PublishRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocialPost:
    """Publish an approved draft now, or schedule it with ``scheduled_for``.
    Instagram uses the rendered recap card as the image."""
    return await _publish(db, user, content_id, body.platform, scheduled_for=body.scheduled_for)


@router.post("/content/{content_id}/publish/instagram", response_model=SocialPostPublic)
async def publish_instagram_with_image(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    image: Annotated[UploadFile, File()],
    scheduled_for: Annotated[datetime | None, Form()] = None,
) -> SocialPost:
    """Publish (or schedule) an approved draft to Instagram with the user's own image."""
    data = await image.read(images.MAX_UPLOAD_BYTES + 1)
    if len(data) > images.MAX_UPLOAD_BYTES:
        raise http_error(status.HTTP_400_BAD_REQUEST, "Images must be 10 MB or smaller.", "image_too_large")
    return await _publish(db, user, content_id, "instagram", upload=data, scheduled_for=scheduled_for)


@router.delete("/social/posts/{post_id}", response_model=SocialPostPublic)
async def cancel_scheduled_post(
    post_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocialPost:
    """Cancel a scheduled post before it is sent."""
    post = (await db.execute(select(SocialPost).where(SocialPost.id == post_id))).scalar_one_or_none()
    if post is None:
        raise http_error(status.HTTP_404_NOT_FOUND, "Post not found", "not_found")
    await _load_piece(db, user, post.content_id, write=True)  # same owner rule as the draft
    try:
        return await sp.cancel(db, post)
    except PublishError as exc:
        raise _http(exc) from exc


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


@router.get("/social/drafts", response_model=list[PublishableDraft])
async def list_publishable_drafts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    platform: Platform | None = None,
) -> list[PublishableDraft]:
    """The signed-in user's own approved social drafts, newest first, with where each
    can go and what happened there."""
    rows = await db.execute(
        select(ContentPiece)
        .outerjoin(Job, Job.id == ContentPiece.job_id)
        .where(
            ContentPiece.status.in_(sp.PUBLIC_STATUSES),
            or_(Job.user_id == user.id, (ContentPiece.job_id.is_(None)) & (ContentPiece.user_id == user.id)),
        )
        .order_by(ContentPiece.created_at.desc())
        .limit(200)
    )
    pieces = []
    for piece in rows.scalars():
        targets = sp.platforms_for_kind(sp.kind_for_type(piece.type))
        if targets and (platform is None or platform in targets):
            pieces.append((piece, targets))
    latest: dict[tuple[UUID, str], SocialPost] = {}
    if pieces:
        posts = await db.execute(
            select(SocialPost)
            .where(SocialPost.content_id.in_([p.id for p, _ in pieces]))
            .order_by(SocialPost.created_at.asc())
        )
        latest = {(s.content_id, s.platform): s for s in posts.scalars()}  # newest wins

    def state(piece_id: UUID, name: str) -> DraftPlatformState:
        post = latest.get((piece_id, name))
        if post is None:
            return DraftPlatformState(status="not_published")
        return DraftPlatformState(status=post.status, post_url=post.post_url, scheduled_for=post.scheduled_for)

    return [
        PublishableDraft(
            content_id=p.id,
            kind=sp.kind_for_type(p.type) or "",
            platforms={name: state(p.id, name) for name in targets},
            title=p.title,
            language=p.language,
            excerpt=plain_text(p.body or "")[:200],
            job_id=p.job_id,
            created_at=p.created_at,
        )
        for p, targets in pieces
    ]


@router.get("/content/{content_id}/publish-preview", response_model=PublishPreview)
async def publish_preview(
    content_id: UUID,
    platform: Platform,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublishPreview:
    """Exactly the text that ``publish`` would send, and anything that would stop it."""
    piece = await _load_piece(db, user, content_id, write=True)
    module = sp.PLATFORMS[platform]
    text = sp.post_text(platform, piece)
    count = module.weighted_length(text) if hasattr(module, "weighted_length") else len(text)
    return PublishPreview(
        platform=platform,
        text=text,
        characters=count,
        limit=module.MAX_TEXT,
        problems=await sp.problems_for(db, user.id, piece, platform),
        image_preview_path=(
            f"{get_settings().api_v1_prefix}/content/{piece.id}/social-image"
            if module.NEEDS_IMAGE
            else None
        ),
    )
