import datetime as dt
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.event import EventType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the event")
    date: dt.date = Field(..., description="Date of the event")
    topic: str | None = Field(None, max_length=255, description="Topic or theme of the event")
    organizer_name: str | None = Field(None, max_length=255, description="Name of the organizer")
    type: EventType = Field(
        default=EventType.OTHER, description="Type of event: meetup, event, speech, other"
    )


class EventCreate(EventBase):
    pass


class EventRead(EventBase, ORMModel):
    id: UUID
    organizer_id: UUID
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
