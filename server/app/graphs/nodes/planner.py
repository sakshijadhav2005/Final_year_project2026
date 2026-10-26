from typing import Any

from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.providers.gemini_llm import analysis_system, build_user_prompt
from app.services.resilience import llm_circuit, with_backoff


async def content_planner(state: JobGraphState) -> dict[str, Any]:
    """Synthesizes topic, highlight, speaker, and sentiment analysis into a master brief.

    The analysis call already returns a brief in most cases; then no extra LLM call is made.
    """
    if isinstance(state.get("brief"), dict) and state.get("brief"):
        return {"brief": state["brief"]}
    llm = get_llm_provider()
    extra = (
        f"Topics={state.get('topics')}\nHighlights={state.get('highlights')}\n"
        f"Speakers={state.get('speakers')}\nSentiment={state.get('sentiment')}\n"
        f"Requested types={state.get('requested_types')}"
    )

    async def _call() -> dict[str, Any]:
        return await llm.generate_json(
            system=analysis_system(),
            user=build_user_prompt("content_planner", state.get("transcript_text", ""), extra),
            temperature=0.2,
        )

    return {"brief": await with_backoff(_call, circuit=llm_circuit)}
