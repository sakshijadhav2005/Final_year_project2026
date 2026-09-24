from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import UserRole
from app.db.session import get_db
from app.middleware.role_guard import require_role
from app.models.event import Event, EventType
from app.models.user import User
from app.schemas.event import EventCreate, EventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[EventRead])
async def list_events(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    type: EventType | None = Query(None, description="Filter events by type"),
) -> list[Event]:
    query = select(Event).order_by(Event.date.desc())
    if type is not None:
        query = query.where(Event.type == type)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    user: Annotated[User, Depends(require_role([UserRole.EVENT_ORGANIZER, UserRole.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    organizer_display_name = body.organizer_name or user.email.split("@")[0]
    new_event = Event(
        name=body.name,
        date=body.date,
        topic=body.topic,
        location=body.location,
        banner_image=body.banner_image,
        description=body.description,
        organizer_name=organizer_display_name,
        type=body.type,
        organizer_id=user.id,
    )
    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)
    return new_event


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    event = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    user: Annotated[User, Depends(require_role([UserRole.EVENT_ORGANIZER, UserRole.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    event = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if user.role != UserRole.ADMIN and event.organizer_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete an event you did not organize",
        )
    await db.delete(event)
    await db.commit()
