from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.job import Job
from app.models.user import AuditLog, User
from app.schemas.common import JobPublic, RolePatch, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


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
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    user.role = body.role
    await db.commit()
    await db.refresh(user)
    return user
