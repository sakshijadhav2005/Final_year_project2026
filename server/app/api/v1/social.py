"""Connect social media accounts and publish approved content to them.

Flow (same for every platform):
1. ``GET /social/{platform}/connect`` (signed in) returns the platform's sign-in URL and
   sets a short-lived nonce cookie. The browser goes to the platform.
2. The platform redirects to ``GET /social/{platform}/callback?code&state``. ``state`` is a
   signed token naming the EventAI user plus the nonce; the nonce must match the cookie, so
   a link crafted by someone else cannot attach their account to this user.
3. ``POST /content/{id}/publish`` posts an *approved* draft to the connected account.
   Instagram needs an image: a recap card is rendered from the flyer copy, or the user
   uploads one with ``POST /content/{id}/publish/instagram``.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.content import PUBLIC_STATUSES, _load_piece
from app.core.config import get_settings
from app.core.exceptions import http_error
from app.core.security import create_token, decode_token
from app.db.session import get_db
from app.models.content import ContentPiece
from app.models.event import Event
from app.models.social import SocialAccount, SocialPost
from app.models.user import User
from app.services.audit import write_audit
from app.services.publishers import SUPPORTED_PLATFORMS, PublishError, images, instagram, linkedin
from app.services.publishers.text import plain_text
from app.services.publishers.tokens import decrypt_token, encrypt_token

router = APIRouter(tags=["social"])

STATE_COOKIE = "eventai_oauth_nonce"
STATE_TTL = timedelta(minutes=10)
IMAGE_LINK_TTL = timedelta(hours=1)
PENDING_WINDOW = timedelta(minutes=10)  # a newer "pending" attempt blocks a second click
Platform = Literal["linkedin", "instagram"]
PLATFORMS: dict[str, ModuleType] = {"linkedin": linkedin, "instagram": instagram}
LABELS = {"linkedin": "LinkedIn", "instagram": "Instagram"}
ENV_HINT = {"linkedin": "LINKEDIN_CLIENT_ID", "instagram": "INSTAGRAM_CLIENT_ID"}

# Not 401 for "reconnect": the web app treats 401 as its own session expiring.
_PUBLISH_ERROR_STATUS = {
    "too_long": status.HTTP_400_BAD_REQUEST,
    "empty_post": status.HTTP_400_BAD_REQUEST,
    "invalid_image": status.HTTP_400_BAD_REQUEST,
    "image_too_large": status.HTTP_400_BAD_REQUEST,
    "reconnect_required": status.HTTP_409_CONFLICT,
    "permission_denied": status.HTTP_409_CONFLICT,
    "not_public": status.HTTP_503_SERVICE_UNAVAILABLE,
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
            configured=PLATFORMS[name].is_configured(),
            account=_account_public(accounts[name]) if name in accounts else None,
        )
        for name in SUPPORTED_PLATFORMS
    ]


@router.get("/social/{platform}/connect", response_model=ConnectResponse)
async def connect(
    platform: Platform, response: Response, user: Annotated[User, Depends(get_current_user)]
) -> ConnectResponse:
    module = PLATFORMS[platform]
    if not module.is_configured():
        raise http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{LABELS[platform]} is not set up on this server ({ENV_HINT[platform]}).",
            "not_configured",
        )
    nonce = secrets.token_urlsafe(24)
    state = create_token(
        subject=str(user.id),
        token_type="oauth_state",
        expires_delta=STATE_TTL,
        extra={"platform": platform, "nonce": nonce},
    )
    response.set_cookie(
        STATE_COOKIE,
        nonce,
        max_age=int(STATE_TTL.total_seconds()),
        httponly=True,
        samesite="lax",  # sent on the top-level redirect back from the platform
        secure=get_settings().is_production,
        path="/api/v1/social",
    )
    return ConnectResponse(authorize_url=module.authorize_url(state))


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
    cookie = request.cookies.get(STATE_COOKIE)
    if not cookie or not secrets.compare_digest(cookie, str(payload.get("nonce", ""))):
        return _settings_redirect(platform, "error", "invalid_state")
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        return _settings_redirect(platform, "error", "invalid_state")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        return _settings_redirect(platform, "error", "invalid_state")

    module = PLATFORMS[platform]
    try:
        tokens = await module.exchange_code(code)
        external_id, name = await module.fetch_identity(tokens.access_token)
    except PublishError as exc:
        return _settings_redirect(platform, "error", exc.code)

    account = await _get_account(db, user.id, platform)
    if account is None:
        account = SocialAccount(user_id=user.id, platform=platform)
        db.add(account)
    account.external_id = external_id
    account.display_name = name
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
    account = await _get_account(db, user.id, platform)
    if account is not None:
        await db.delete(account)
        await write_audit(
            db, user_id=user.id, action="social_disconnect", resource_type="social_account",
            resource_id=platform,
        )
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _reconnect(platform: str) -> PublishError:
    label = LABELS[platform]
    return PublishError(
        f"Your {label} connection expired. Reconnect {label} in Settings.", "reconnect_required"
    )


async def _access_token(account: SocialAccount) -> str:
    """A usable token, refreshed when the platform allows it. Updates ``account`` in place."""
    token = decrypt_token(account.access_token_enc)
    if token is None:
        raise _reconnect(account.platform)
    expired = _is_expired(account)

    if account.platform == "instagram":
        if expired:
            raise _reconnect("instagram")
        if not instagram.needs_refresh(_aware(account.expires_at)):
            return token
        try:
            fresh = await instagram.refresh(token)
        except PublishError:
            return token  # still valid for a while; try refreshing next time
    else:
        if not expired:
            return token
        refresh_token = decrypt_token(account.refresh_token_enc) if account.refresh_token_enc else None
        if not refresh_token:
            raise _reconnect(account.platform)
        fresh = await linkedin.refresh(refresh_token)
        if fresh.refresh_token:
            account.refresh_token_enc = encrypt_token(fresh.refresh_token)

    account.access_token_enc = encrypt_token(fresh.access_token)
    account.expires_at = (
        datetime.now(UTC) + timedelta(seconds=fresh.expires_in) if fresh.expires_in else None
    )
    return fresh.access_token


# ── Instagram images ───────────────────────────────────────────────────────────


async def _card_for(db: AsyncSession, piece: ContentPiece) -> images.CardContent:
    """Recap card text: the session's flyer copy when there is one, else the caption."""
    flyer = None
    if piece.job_id is not None:
        rows = await db.execute(select(ContentPiece).where(ContentPiece.job_id == piece.job_id))
        flyer = next(
            (p for p in rows.scalars() if "flyer" in p.type.lower() and p.language == piece.language),
            None,
        )
    data = (flyer.structured if flyer and isinstance(flyer.structured, dict) else {}) or {}
    caption_lines = [ln for ln in plain_text(piece.body or "").splitlines() if ln.strip()]
    headline = str(data.get("headline") or (flyer.title if flyer else None) or piece.title or "").strip()
    if not headline and caption_lines:
        headline = caption_lines.pop(0)
    subhead = str(data.get("subhead") or (caption_lines[0] if caption_lines else ""))
    bullets = [str(b) for b in data.get("bullets") or []] if isinstance(data.get("bullets"), list) else []

    footer_bits = [str(data[k]) for k in ("date", "location") if data.get(k)]
    if not footer_bits and piece.event_id is not None:
        event = (await db.execute(select(Event).where(Event.id == piece.event_id))).scalar_one_or_none()
        if event is not None:
            footer_bits = [b for b in (event.name, str(event.date or "")[:10], event.location) if b]
    return images.CardContent(headline, subhead, bullets, " · ".join(footer_bits))


def _check_public_images_possible() -> None:
    settings = get_settings()
    if settings.storage_backend in ("r2", "s3") or settings.public_base_url:
        return
    raise PublishError(
        "Instagram downloads the image from a public https URL, and this server has none. "
        "Set STORAGE_BACKEND=r2 (with R2 keys) or PUBLIC_BASE_URL (e.g. an ngrok https URL).",
        "not_public",
    )


def _public_image_url(post: SocialPost) -> str:
    from app.services.storage import get_storage

    uri = post.image_uri or ""
    if uri.startswith("s3://"):
        url = get_storage().get_access_url(uri, expires_in=int(IMAGE_LINK_TTL.total_seconds()))
        if url.startswith("https://"):
            return url
    base = get_settings().public_base_url.rstrip("/")
    if not base:
        _check_public_images_possible()
        raise PublishError("Could not make a public link to the image.", "not_public")
    token = create_token(subject=str(post.id), token_type="social_media", expires_delta=IMAGE_LINK_TTL)
    return f"{base}{get_settings().api_v1_prefix}/social/media/{token}"


@router.get("/content/{content_id}/social-image")
async def preview_social_image(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """The recap card that "Publish to Instagram" uses when no image is uploaded."""
    piece = await _load_piece(db, user, content_id, write=True)
    data = images.render_card(await _card_for(db, piece))
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
    db: AsyncSession, user: User, content_id: UUID, platform: str, upload: bytes | None = None
) -> SocialPost:
    piece = await _load_piece(db, user, content_id, write=True)
    if piece.status not in PUBLIC_STATUSES:
        raise http_error(
            status.HTTP_409_CONFLICT, "Approve this draft before publishing it.", "not_approved"
        )
    label = LABELS[platform]
    earlier = (
        await db.execute(
            select(SocialPost).where(
                SocialPost.content_id == piece.id,
                SocialPost.platform == platform,
                SocialPost.status.in_(("posted", "pending")),
            )
        )
    ).scalars().all()
    now = datetime.now(UTC)
    if any(
        p.status == "posted" or (_aware(p.created_at) or now) > now - PENDING_WINDOW for p in earlier
    ):
        raise http_error(
            status.HTTP_409_CONFLICT,
            f"This draft is already published (or being published) to {label}.",
            "already_published",
        )
    account = await _get_account(db, user.id, platform)
    if account is None:
        raise http_error(
            status.HTTP_400_BAD_REQUEST, f"Connect your {label} account in Settings first.", "not_connected"
        )

    # Saved before calling the platform: Instagram fetches the image through this row.
    post = SocialPost(id=uuid.uuid4(), content_id=piece.id, user_id=user.id, platform=platform)
    try:
        if platform == "instagram":
            caption = instagram.build_caption(piece.body or "")
            instagram.check_caption(caption)
            _check_public_images_possible()
            jpeg = images.normalize_upload(upload) if upload else images.render_card(
                await _card_for(db, piece)
            )
            from app.services.storage import get_storage

            post.image_uri = get_storage().save_bytes(jpeg, f"social_{post.id.hex}.jpg")
        db.add(post)
        await db.commit()

        token = await _access_token(account)
        if platform == "instagram":
            result = await instagram.publish(token, account.external_id, _public_image_url(post), caption)
        else:
            text = linkedin.build_post_text(piece.title, piece.body or "")
            result = await linkedin.publish(token, account.external_id, text)
    except PublishError as exc:
        post.status = "failed"
        post.error = str(exc)
        db.add(post)
        await write_audit(
            db, user_id=user.id, action="publish_failed", resource_type="content",
            resource_id=str(piece.id), detail=f"{platform}: {exc.code}",
        )
        await db.commit()
        raise http_error(_PUBLISH_ERROR_STATUS.get(exc.code, 502), str(exc), exc.code) from exc
    except Exception:
        post.status = "failed"
        post.error = "Unexpected error while publishing"
        await db.commit()
        raise

    post.status = "posted"
    post.external_post_id = result.external_post_id
    post.post_url = result.post_url
    await write_audit(
        db, user_id=user.id, action="publish", resource_type="content",
        resource_id=str(piece.id), detail=f"{platform}: {result.external_post_id}",
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.post("/content/{content_id}/publish", response_model=SocialPostPublic)
async def publish_content(
    content_id: UUID,
    body: PublishRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocialPost:
    """Publish an approved draft. Instagram uses the rendered recap card as the image."""
    return await _publish(db, user, content_id, body.platform)


@router.post("/content/{content_id}/publish/instagram", response_model=SocialPostPublic)
async def publish_instagram_with_image(
    content_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    image: Annotated[UploadFile, File()],
) -> SocialPost:
    """Publish an approved draft to Instagram with the user's own image."""
    data = await image.read(images.MAX_UPLOAD_BYTES + 1)
    if len(data) > images.MAX_UPLOAD_BYTES:
        raise http_error(status.HTTP_400_BAD_REQUEST, "Images must be 10 MB or smaller.", "image_too_large")
    return await _publish(db, user, content_id, "instagram", upload=data)


def platform_for_type(content_type: str) -> str | None:
    """Which platform a draft type is written for (same rule as the Content Studio)."""
    t = (content_type or "").lower().replace("-", "").replace("_", "")
    if "linkedin" in t:
        return "linkedin"
    if "insta" in t:
        return "instagram"
    return None


class PublishableDraft(BaseModel):
    content_id: UUID
    platform: str
    title: str | None
    language: str
    excerpt: str
    job_id: UUID | None
    created_at: datetime | None
    published_url: str | None  # set once it is live


class PublishPreview(BaseModel):
    platform: str
    text: str
    characters: int
    limit: int
    problems: list[str]
    image_preview_path: str | None  # Instagram: GET this (signed in) for the recap card


@router.get("/social/drafts", response_model=list[PublishableDraft])
async def list_publishable_drafts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    platform: Platform | None = None,
) -> list[PublishableDraft]:
    """The signed-in user's own approved LinkedIn / Instagram drafts, newest first."""
    from sqlalchemy import or_

    from app.models.job import Job

    rows = await db.execute(
        select(ContentPiece)
        .outerjoin(Job, Job.id == ContentPiece.job_id)
        .where(
            ContentPiece.status.in_(PUBLIC_STATUSES),
            or_(Job.user_id == user.id, (ContentPiece.job_id.is_(None)) & (ContentPiece.user_id == user.id)),
        )
        .order_by(ContentPiece.created_at.desc())
        .limit(200)
    )
    pieces = [(p, platform_for_type(p.type)) for p in rows.scalars()]
    pieces = [(p, plat) for p, plat in pieces if plat and (platform is None or plat == platform)]
    live: dict[tuple[UUID, str], str | None] = {}
    if pieces:
        posted = await db.execute(
            select(SocialPost).where(
                SocialPost.content_id.in_([p.id for p, _ in pieces]), SocialPost.status == "posted"
            )
        )
        live = {(s.content_id, s.platform): s.post_url or "" for s in posted.scalars()}
    return [
        PublishableDraft(
            content_id=p.id,
            platform=plat,
            title=p.title,
            language=p.language,
            excerpt=plain_text(p.body or "")[:200],
            job_id=p.job_id,
            created_at=p.created_at,
            published_url=live.get((p.id, plat)),
        )
        for p, plat in pieces
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
    problems: list[str] = []
    if piece.status not in PUBLIC_STATUSES:
        problems.append("The draft is not approved yet.")
    if platform == "instagram":
        text, limit = instagram.build_caption(piece.body or ""), instagram.MAX_CAPTION_CHARS
        try:
            instagram.check_caption(text)
            _check_public_images_possible()
        except PublishError as exc:
            problems.append(str(exc))
    else:
        text = linkedin.build_post_text(piece.title, piece.body or "")
        limit = linkedin.MAX_COMMENTARY_CHARS
        if len(text) > limit:
            problems.append(f"Too long for LinkedIn ({len(text)}/{limit} characters).")
    if not text.strip():
        problems.append("The post is empty.")
    account = await _get_account(db, user.id, platform)
    if account is None:
        problems.append(f"{LABELS[platform]} is not connected (Settings -> Connected accounts).")
    elif _is_expired(account) and not account.refresh_token_enc:
        problems.append(f"The {LABELS[platform]} connection expired; reconnect it in Settings.")
    return PublishPreview(
        platform=platform,
        text=text,
        characters=len(text),
        limit=limit,
        problems=problems,
        image_preview_path=(
            f"{get_settings().api_v1_prefix}/content/{piece.id}/social-image"
            if platform == "instagram"
            else None
        ),
    )


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
