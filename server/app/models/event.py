import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Uuid
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import TimestampMixin


class EventType(str, enum.Enum):
    MEETUP = "meetup"
    EVENT = "event"
    SPEECH = "speech"
    OTHER = "other"


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organizer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[EventType] = mapped_column(
        SqlEnum(EventType, native_enum=False), nullable=False, default=EventType.OTHER
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    organizer = relationship("User", backref="events")
    content_pieces = relationship("ContentPiece", backref="event", cascade="all, delete-orphan")
