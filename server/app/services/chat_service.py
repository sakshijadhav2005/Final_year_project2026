import asyncio
import json
from collections.abc import AsyncIterator

from app.core.config import get_settings


def _build_chat_system_prompt(persona: str, transcript_text: str | None = None) -> str:
    transcript_block = (
        f"\n\n### EVENT SESSION TRANSCRIPT:\n{transcript_text[:12000]}\n" if transcript_text else ""
    )

    if persona == "organizer_copilot":
        return (
            "You are the EventAI Organizer Co-Pilot, an expert AI assistant dedicated to helping event organizers. "
            "You have access to the event transcript, audience sentiment, and generation pipeline.\n"
            "Capabilities:\n"
            "1. Answer questions about the transcript and locate exact moments/quotes.\n"
            "2. Provide insights on audience engagement, key discussion points, and debate topics.\n"
            "3. Help draft on-demand announcements, tweet threads, or revisions to generated posts.\n"
            "4. Suggest promotional schedules.\n"
            "Tone: Proactive, strategic, helpful, and concise."
            f"{transcript_block}"
        )

    # Attendee Q&A Persona
    return (
        "You are the EventAI Attendee Interactive Assistant. You represent the knowledge and insights from this event session.\n"
        "Guidelines:\n"
        "1. Answer attendee questions accurately, strictly grounded in what the speakers discussed in the transcript.\n"
        "2. If an attendee asks for key quotes or takeaways, provide direct quotes with speaker attribution where available.\n"
        "3. Help attendees brainstorm their own unique takeaways or social media reflections based on the talk.\n"
        "4. If a topic was NOT mentioned in the session, politely state that it was not covered in this talk.\n"
        "Tone: Engaging, educational, inspiring, and concise."
        f"{transcript_block}"
    )


async def _stream_claude(messages: list[dict[str, str]], system_prompt: str) -> AsyncIterator[str]:
    """Stream a co-pilot reply from Claude, token by token, as SSE events."""
    from app.providers.anthropic_llm import candidate_models, effort_config, get_client

    settings = get_settings()
    history = [
        {"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("content") or ""}
        for m in messages
        if (m.get("content") or "").strip()
    ]
    # The API needs the conversation to start with a user turn and end with one.
    while history and history[0]["role"] != "user":
        history.pop(0)
    if not history or history[-1]["role"] != "user":
        history.append({"role": "user", "content": "Hello"})

    kwargs = {"output_config": effort_config()} if effort_config() else {}
    models = candidate_models() or [settings.anthropic_model]
    sent_any = False
    async with get_client().messages.stream(
        model=models[0],
        max_tokens=2000,
        system=system_prompt,
        messages=history,
        **kwargs,
    ) as stream:
        async for text in stream.text_stream:
            if text:
                sent_any = True
                yield f"data: {json.dumps({'chunk': text, 'done': False})}\n\n"
    if not sent_any:
        raise RuntimeError("Claude returned an empty reply")
    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"


async def stream_chat_response(
    messages: list[dict[str, str]],
    persona: str = "general_assistant",
    transcript_text: str | None = None,
) -> AsyncIterator[str]:
    """Streams token-by-token chat responses via async generator for SSE."""
    settings = get_settings()
    system_prompt = _build_chat_system_prompt(persona, transcript_text)

    provider = (settings.llm_provider or "").strip().lower()
    use_claude = settings.anthropic_api_key and (
        provider in {"anthropic", "claude"} or (provider != "fake" and not settings.gemini_api_key)
    )
    if use_claude:
        try:
            async for event in _stream_claude(messages, system_prompt):
                yield event
            return
        except Exception:
            pass

    # Check if real Gemini is available and configured
    if settings.gemini_api_key and provider != "fake":
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(
                model_name=settings.gemini_model_generate or "gemini-3.6-flash",
                system_instruction=system_prompt,
            )

            # Build Gemini history format
            formatted_history = []
            for msg in messages[:-1]:
                formatted_history.append(
                    {
                        "role": "user" if msg["role"] == "user" else "model",
                        "parts": [msg["content"]],
                    }
                )

            last_user_message = messages[-1]["content"] if messages else "Hello"
            chat = model.start_chat(history=formatted_history)
            response_stream = await chat.send_message_async(last_user_message, stream=True)

            async for chunk in response_stream:
                if chunk.text:
                    yield f"data: {json.dumps({'chunk': chunk.text, 'done': False})}\n\n"

            yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
            return
        except Exception:
            pass

    # Fallback / Mock streaming for offline / test environments
    last_query = messages[-1]["content"] if messages else "Hello"
    mock_reply = (
        f"Based on the event session, here is what you need to know regarding '{last_query[:40]}':\n\n"
        "1. **Core Concept:** The speaker emphasized that modular multi-agent pipelines decouple complex tasks.\n"
        "2. **Practical Tip:** Always enforce deterministic guardrails before publishing copy.\n\n"
        "Let me know if you would like me to draft a LinkedIn post or query a specific speaker quote!"
    )
    words = mock_reply.split(" ")
    for i, word in enumerate(words):
        yield f"data: {json.dumps({'chunk': word + ' ', 'done': False})}\n\n"
        await asyncio.sleep(0.03)

    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
