import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.models.recording import Recording
from app.models.user import User
from app.schemas.chat import (
    ChatMessageSend,
    ChatSessionCreate,
    ChatSessionPublic,
)
from app.services.chat_service import stream_chat_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionPublic, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    body: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    session = ChatSession(
        user_id=current_user.id,
        event_id=body.event_id,
        title=body.title,
        persona=body.persona,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[ChatSessionPublic])
async def list_chat_sessions(
    event_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatSession]:
    query = select(ChatSession).where(ChatSession.user_id == current_user.id)
    if event_id:
        query = query.where(ChatSession.event_id == event_id)
    query = query.order_by(ChatSession.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/sessions/{session_id}", response_model=ChatSessionPublic)
async def get_chat_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    session = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    return session


@router.post("/stream")
async def stream_message(
    body: ChatMessageSend,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == body.session_id, ChatSession.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.commit()

    # Fetch transcript if event_id is available
    transcript_text = None
    target_event_id = body.event_id or session.event_id
    if target_event_id:
        recording = (
            (await db.execute(select(Recording).where(Recording.event_id == target_event_id)))
            .scalars()
            .first()
        )
        if recording and hasattr(recording, "transcript_text"):
            transcript_text = recording.transcript_text

    # Build history
    history = [{"role": msg.role, "content": msg.content} for msg in session.messages]
    history.append({"role": "user", "content": body.message})
    session_id = session.id
    persona = body.persona or session.persona

    async def _generator():
        full_reply = []
        async for chunk_str in stream_chat_response(
            messages=history,
            persona=persona,
            transcript_text=transcript_text,
        ):
            yield chunk_str
            if chunk_str.startswith("data: "):
                try:
                    payload = json.loads(chunk_str[6:].strip())
                    if payload.get("chunk"):
                        full_reply.append(payload["chunk"])
                except Exception:
                    pass

        # Save assistant message in isolated session
        assistant_text = "".join(full_reply).strip()
        if assistant_text:
            try:
                async with SessionLocal() as write_db:
                    write_db.add(
                        ChatMessage(session_id=session_id, role="assistant", content=assistant_text)
                    )
                    await write_db.commit()
            except Exception:
                pass

    return StreamingResponse(_generator(), media_type="text/event-stream")
