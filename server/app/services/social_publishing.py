"""Publishing approved drafts to social platforms: checks, sending, scheduling.

Used by the API (publish now / schedule / cancel), by the scheduler loop that sends due
posts, and by the chat co-pilot (read-only status). Ownership of the draft is checked by
the caller; everything else (approval, connection, platform rules, no double posting)
is enforced here, so every path follows the same rules.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_token
from app.models.content import ContentPiece
from app.models.event import Event
from app.models.social import SocialAccount, SocialPost
from app.services.audit import write_audit
from app.services.publishers import (
    SUPPORTED_PLATFORMS,
    PublishError,
    facebook,
    images,
    instagram,
    linkedin,
    x,
)
from app.services.publishers.text import plain_text
from app.services.publishers.tokens import decrypt_token, encrypt_token

logger = structlog.get_logger("social_publishing")

PLATFORMS: dict[str, ModuleType] = {m.NAME: m for m in (linkedin, instagram, facebook, x)}
assert tuple(PLATFORMS) == SUPPORTED_PLATFORMS

PUBLIC_STATUSES = ("approved", "ready_to_publish")
IMAGE_LINK_TTL = timedelta(hours=1)
PENDING_WINDOW = timedelta(minutes=10)  # a newer "pending" attempt blocks a second click
MIN_SCHEDULE_AHEAD = timedelta(minutes=1)
MAX_SCHEDULE_AHEAD = timedelta(days=60)  # tokens of most platforms last about 60 days
ACTIVE_STATUSES = ("posted", "pending", "scheduled")


def kind_for_type(content_type: str) -> str | None:
    """Which social format a draft type is (same rule as the Content Studio)."""
    t = (content_type or "").lower().replace("-", "").replace("_", "")
    if "linkedin" in t:
        return "linkedin"
    if "insta" in t or t.startswith("ig"):
        return "instagram"
    if t in {"x", "xpost", "tweet", "twitter", "twitterpost"}:
        return "x"
    return None


def platforms_for_kind(kind: str | None) -> list[str]:
    return [name for name, module in PLATFORMS.items() if kind in module.ACCEPTS]


def aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything is stored in UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def is_expired(account: SocialAccount) -> bool:
    expires = aware(account.expires_at)
    return expires is not None and expires <= datetime.now(UTC)


def connection_usable(account: SocialAccount | None) -> bool:
    return account is not None and (not is_expired(account) or bool(account.refresh_token_enc))


async def get_account(db: AsyncSession, user_id: UUID, platform: str) -> SocialAccount | None:
    return (
        await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id, SocialAccount.platform == platform
            )
        )
    ).scalar_one_or_none()


def reconnect_error(platform: str) -> PublishError:
    label = PLATFORMS[platform].LABEL
    return PublishError(
        f"Your {label} connection expired. Reconnect {label} in Settings.", "reconnect_required"
    )


async def access_token(account: SocialAccount) -> str:
    """A usable token, refreshed when the platform allows it. Updates ``account`` in place."""
    module = PLATFORMS[account.platform]
    token = decrypt_token(account.access_token_enc)
    if token is None:
        raise reconnect_error(account.platform)
    expired = is_expired(account)

    if module.REFRESH == "self":  # Instagram: swap the long-lived token before it runs out
        if expired:
            raise reconnect_error(account.platform)
        if not module.needs_refresh(aware(account.expires_at)):
            return token
        try:
            fresh = await module.refresh(token)
        except PublishError:
            return token  # still valid for a while; try again next time
    elif module.REFRESH == "refresh_token":
        if not expired:
            return token
        refresh_token = decrypt_token(account.refresh_token_enc) if account.refresh_token_enc else None
        if not refresh_token:
            raise reconnect_error(account.platform)
        fresh = await module.refresh(refresh_token)
        if fresh.refresh_token:
            account.refresh_token_enc = encrypt_token(fresh.refresh_token)
    else:
        if expired:
            raise reconnect_error(account.platform)
        return token

    account.access_token_enc = encrypt_token(fresh.access_token)
    account.expires_at = (
        datetime.now(UTC) + timedelta(seconds=fresh.expires_in) if fresh.expires_in else None
    )
    return fresh.access_token


# ── Instagram images ───────────────────────────────────────────────────────────


async def card_for(db: AsyncSession, piece: ContentPiece) -> images.CardContent:
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


def check_public_images_possible() -> None:
    settings = get_settings()
    if settings.storage_backend in ("r2", "s3") or settings.public_base_url:
        return
    raise PublishError(
        "Instagram downloads the image from a public https URL, and this server has none. "
        "Set STORAGE_BACKEND=r2 (with R2 keys) or PUBLIC_BASE_URL (e.g. an ngrok https URL).",
        "not_public",
    )


def public_image_url(post: SocialPost) -> str:
    from app.services.storage import get_storage

    uri = post.image_uri or ""
    if uri.startswith("s3://"):
        url = get_storage().get_access_url(uri, expires_in=int(IMAGE_LINK_TTL.total_seconds()))
        if url.startswith("https://"):
            return url
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    if not base:
        check_public_images_possible()
        raise PublishError("Could not make a public link to the image.", "not_public")
    token = create_token(subject=str(post.id), token_type="social_media", expires_delta=IMAGE_LINK_TTL)
    return f"{base}{settings.api_v1_prefix}/social/media/{token}"


# ── Checks, sending, scheduling ────────────────────────────────────────────────


def post_text(platform: str, piece: ContentPiece) -> str:
    return PLATFORMS[platform].build_text(piece.title, piece.body or "")


async def problems_for(
    db: AsyncSession, user_id: UUID, piece: ContentPiece, platform: str
) -> list[str]:
    """Everything that would stop ``piece`` from being published to ``platform`` now."""
    module = PLATFORMS[platform]
    problems: list[str] = []
    if piece.status not in PUBLIC_STATUSES:
        problems.append("The draft is not approved yet.")
    kind = kind_for_type(piece.type)
    if kind not in module.ACCEPTS:
        problems.append(f"{module.LABEL} takes {', '.join(sorted(module.ACCEPTS))} drafts, not this one.")
    try:
        module.check_text(post_text(platform, piece))
        if module.NEEDS_IMAGE:
            check_public_images_possible()
    except PublishError as exc:
        problems.append(str(exc))
    if not module.is_configured():
        problems.append(f"{module.LABEL} is not set up on this server ({module.ENV_HINT}).")
    account = await get_account(db, user_id, platform)
    if account is None:
        problems.append(f"{module.LABEL} is not connected (Settings -> Connected accounts).")
    elif not connection_usable(account):
        problems.append(f"The {module.LABEL} connection expired; reconnect it in Settings.")
    return problems


async def prepare(
    db: AsyncSession,
    user_id: UUID,
    piece: ContentPiece,
    platform: str,
    *,
    upload: bytes | None = None,
    scheduled_for: datetime | None = None,
) -> tuple[SocialPost, SocialAccount]:
    """Validate and create the post row (``scheduled`` or ``pending``). Commits it.

    Raises PublishError with a code the API maps to an HTTP status."""
    module = PLATFORMS[platform]
    if piece.status not in PUBLIC_STATUSES:
        raise PublishError("Approve this draft before publishing it.", "not_approved")
    if kind_for_type(piece.type) not in module.ACCEPTS:
        raise PublishError(
            f"{module.LABEL} takes {', '.join(sorted(module.ACCEPTS))} drafts, not this one.",
            "wrong_type",
        )
    if upload is not None and not module.NEEDS_IMAGE:
        raise PublishError(f"{module.LABEL} posts here are text only.", "invalid_image")
    now = datetime.now(UTC)
    if scheduled_for is not None:
        scheduled_for = aware(scheduled_for).astimezone(UTC)
        if scheduled_for < now + MIN_SCHEDULE_AHEAD:
            raise PublishError("Pick a time at least a minute from now.", "invalid_schedule")
        if scheduled_for > now + MAX_SCHEDULE_AHEAD:
            raise PublishError("Posts can be scheduled up to 60 days ahead.", "invalid_schedule")

    earlier = (
        await db.execute(
            select(SocialPost).where(
                SocialPost.content_id == piece.id,
                SocialPost.platform == platform,
                SocialPost.status.in_(ACTIVE_STATUSES),
            )
        )
    ).scalars().all()
    for p in earlier:
        if p.status == "posted":
            raise PublishError(f"This draft is already published to {module.LABEL}.", "already_published")
        if p.status == "scheduled":
            raise PublishError(
                f"This draft is already scheduled for {module.LABEL}. Cancel that first.",
                "already_published",
            )
        if (aware(p.updated_at) or now) > now - PENDING_WINDOW:
            raise PublishError(f"This draft is being published to {module.LABEL}.", "already_published")

    account = await get_account(db, user_id, platform)
    if account is None:
        raise PublishError(f"Connect your {module.LABEL} account in Settings first.", "not_connected")
    if not connection_usable(account):
        raise reconnect_error(platform)
    module.check_text(post_text(platform, piece))

    post = SocialPost(
        id=uuid.uuid4(),
        content_id=piece.id,
        user_id=user_id,
        platform=platform,
        status="scheduled" if scheduled_for else "pending",
        scheduled_for=scheduled_for,
    )
    if module.NEEDS_IMAGE:
        check_public_images_possible()
        jpeg = images.normalize_upload(upload) if upload else images.render_card(await card_for(db, piece))
        from app.services.storage import get_storage

        post.image_uri = get_storage().save_bytes(jpeg, f"social_{post.id.hex}.jpg")
    db.add(post)
    if scheduled_for:
        await write_audit(
            db, user_id=user_id, action="publish_scheduled", resource_type="content",
            resource_id=str(piece.id), detail=f"{platform}: {scheduled_for.isoformat()}",
        )
    # Committed before calling the platform: Instagram fetches the image through this row.
    await db.commit()
    return post, account


async def _fail(db: AsyncSession, post: SocialPost, message: str, code: str) -> None:
    post.status = "failed"
    post.error = message
    await write_audit(
        db, user_id=post.user_id, action="publish_failed", resource_type="content",
        resource_id=str(post.content_id), detail=f"{post.platform}: {code}",
    )
    await db.commit()


async def send(
    db: AsyncSession, post: SocialPost, piece: ContentPiece, account: SocialAccount
) -> SocialPost:
    """Publish a ``pending`` post now. Records the outcome; re-raises PublishError."""
    module = PLATFORMS[post.platform]
    try:
        if piece.status not in PUBLIC_STATUSES:  # rejected after it was scheduled
            raise PublishError("The draft is no longer approved.", "not_approved")
        text = post_text(post.platform, piece)
        token = await access_token(account)
        if module.NEEDS_IMAGE:
            result = await module.publish(token, account.external_id, public_image_url(post), text)
        else:
            result = await module.publish(token, account.external_id, text)
    except PublishError as exc:
        await _fail(db, post, str(exc), exc.code)
        raise
    except Exception:
        await _fail(db, post, "Unexpected error while publishing", "internal_error")
        raise

    post.status = "posted"
    post.external_post_id = result.external_post_id
    post.post_url = result.post_url
    post.error = None
    await write_audit(
        db, user_id=post.user_id, action="publish", resource_type="content",
        resource_id=str(piece.id), detail=f"{post.platform}: {result.external_post_id}",
    )
    await db.commit()
    await db.refresh(post)
    return post


async def cancel(db: AsyncSession, post: SocialPost) -> SocialPost:
    if post.status != "scheduled":
        raise PublishError("Only scheduled posts can be cancelled.", "not_scheduled")
    post.status = "cancelled"
    await write_audit(
        db, user_id=post.user_id, action="publish_cancelled", resource_type="content",
        resource_id=str(post.content_id), detail=post.platform,
    )
    await db.commit()
    await db.refresh(post)
    return post


async def run_due_posts(now: datetime | None = None) -> int:
    """Send every scheduled post whose time has come. Returns how many were attempted.

    Each post is claimed with a conditional UPDATE, so two workers never send it twice."""
    from app.db.session import SessionLocal

    now = now or datetime.now(UTC)
    attempted = 0
    async with SessionLocal() as db:
        due = (
            await db.execute(
                select(SocialPost.id).where(
                    SocialPost.status == "scheduled", SocialPost.scheduled_for <= now
                )
            )
        ).scalars().all()
        for post_id in due:
            claimed = await db.execute(
                update(SocialPost)
                .where(SocialPost.id == post_id, SocialPost.status == "scheduled")
                .values(status="pending")
            )
            await db.commit()
            if claimed.rowcount != 1:
                continue
            attempted += 1
            post = (await db.execute(select(SocialPost).where(SocialPost.id == post_id))).scalar_one()
            piece = (
                await db.execute(select(ContentPiece).where(ContentPiece.id == post.content_id))
            ).scalar_one_or_none()
            account = await get_account(db, post.user_id, post.platform)
            if piece is None or account is None:
                await _fail(db, post, "The draft or the connected account no longer exists.", "gone")
                continue
            try:
                await send(db, post, piece, account)
                logger.info("scheduled_post_sent", post_id=str(post.id), platform=post.platform)
            except PublishError as exc:
                logger.warning("scheduled_post_failed", post_id=str(post.id), code=exc.code)
            except Exception as exc:  # noqa: BLE001 - one bad post must not stop the others
                logger.error("scheduled_post_crashed", post_id=str(post.id), error=str(exc))
    return attempted


async def run_scheduler_periodically() -> None:
    """In-process scheduler loop (used when Celery beat is not running)."""
    interval = max(5, get_settings().social_scheduler_interval_seconds)
    while True:
        try:
            await run_due_posts()
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            logger.error("social_scheduler_error", error=str(exc))
        await asyncio.sleep(interval)


async def status_summary(db: AsyncSession, user_id: UUID, pieces: list[ContentPiece]) -> list[dict]:
    """Per draft: where it can go and what happened there. Used by the chat co-pilot."""
    if not pieces:
        return []
    posts = (
        await db.execute(
            select(SocialPost)
            .where(SocialPost.content_id.in_([p.id for p in pieces]))
            .order_by(SocialPost.created_at.desc())
        )
    ).scalars().all()
    accounts = {
        a.platform: a
        for a in (await db.execute(select(SocialAccount).where(SocialAccount.user_id == user_id))).scalars()
    }
    out = []
    for piece in pieces:
        kind = kind_for_type(piece.type)
        targets = platforms_for_kind(kind)
        if not targets:
            continue
        state = {}
        for platform in targets:
            latest = next((p for p in posts if p.content_id == piece.id and p.platform == platform), None)
            state[platform] = {
                "connected": connection_usable(accounts.get(platform)),
                "status": latest.status if latest else "not_published",
                "scheduled_for": aware(latest.scheduled_for).isoformat() if latest and latest.scheduled_for else None,
                "post_url": latest.post_url if latest else None,
            }
        out.append(
            {"title": piece.title, "kind": kind, "approved": piece.status in PUBLIC_STATUSES, "platforms": state}
        )
    return out
