from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChatMessagePublic(ORMModel):
    id: UUID
    session_id: UUID
    role: str  # "user" | "assistant" | "system"
    content: str
    citations: list[dict] | None = None
    created_at: datetime | None = None


class ChatSessionPublic(ORMModel):
    id: UUID
    user_id: UUID
    event_id: UUID | None = None
    title: str
    persona: str = "general_assistant"  # "organizer_copilot" | "attendee_qa"
    created_at: datetime | None = None
    messages: list[ChatMessagePublic] = []


class ChatSessionCreate(BaseModel):
    event_id: UUID | None = None
    title: str = Field(default="New Chat", max_length=255)
    persona: str = Field(default="general_assistant", max_length=32)


class ChatMessageSend(BaseModel):
    # session_id is optional: the UI widgets start chatting without creating a
    # session first, so the server creates one on the first message.
    session_id: UUID | None = None
    message: str = Field(..., min_length=1, max_length=4000)
    event_id: UUID | None = None
    job_id: UUID | None = None
    persona: str | None = Field(default=None, max_length=32)
    # The React client sends "context_type"; treat it as an alias of persona.
    context_type: str | None = Field(default=None, max_length=32)

    @property
    def resolved_persona(self) -> str | None:
        return self.persona or self.context_type
