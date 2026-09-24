from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.job import Job
from app.models.user import AuditLog, User
from app.schemas.common import JobPublic, RolePatch, UserPublic
from app.services.audit import write_audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserPublic])
async def admin_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    return list(result.scalars().all())


@router.get("/jobs", response_model=list[JobPublic])
async def admin_jobs(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Job]:
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    return list(result.scalars().all())


@router.get("/audit")
async def admin_audit(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id) if row.user_id else None,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "detail": row.detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/users/{user_id}/role", response_model=UserPublic)
async def set_role(
    user_id: UUID,
    body: RolePatch,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    settings = get_settings()

    target_user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Admin cannot change their own role
    if target_user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot modify their own role",
        )

    # Bootstrap admin cannot have their role changed
    if target_user.email.lower() == settings.bootstrap_admin_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The bootstrap administrator role cannot be modified",
        )

    previous_role = target_user.role
    target_user.role = body.role.value if hasattr(body.role, "value") else str(body.role)

    await write_audit(
        db,
        user_id=current_admin.id,
        action="role_change",
        resource_type="user",
        resource_id=str(target_user.id),
        detail=f"Role changed from {previous_role} to {target_user.role}",
    )

    await db.commit()
    await db.refresh(target_user)
    return target_user
