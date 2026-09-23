import asyncio
from typing import Any

from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.providers.gemini_llm import analysis_system, build_user_prompt
from app.services.resilience import llm_circuit, with_backoff


async def _agent(task: str, state: JobGraphState, temperature: float = 0.2) -> dict[str, Any]:
    llm = get_llm_provider()

    async def _call() -> dict[str, Any]:
        return await llm.generate_json(
            system=analysis_system(),
            user=build_user_prompt(task, state.get("transcript_text", "")),
            temperature=temperature,
        )

    return await with_backoff(_call, circuit=llm_circuit)


async def fan_out(state: JobGraphState) -> dict[str, Any]:
    return {"route": state.get("route") or "continue"}


async def topic_extraction(state: JobGraphState) -> dict[str, Any]:
    return {"topics": await _agent("topic_extraction", state)}


async def highlight_detection(state: JobGraphState) -> dict[str, Any]:
    return {"highlights": await _agent("highlight_detection", state)}


async def speaker_analysis(state: JobGraphState) -> dict[str, Any]:
    return {"speakers": await _agent("speaker_analysis", state)}


async def sentiment_analysis(state: JobGraphState) -> dict[str, Any]:
    return {"sentiment": await _agent("sentiment_analysis", state)}


async def parallel_analysis(state: JobGraphState) -> dict[str, Any]:
    """Runs parallel extraction fan-out nodes (topics, highlights, speakers, sentiment) concurrently."""
    topics_res, highlights_res, speakers_res, sentiment_res = await asyncio.gather(
        _agent("topic_extraction", state),
        _agent("highlight_detection", state),
        _agent("speaker_analysis", state),
        _agent("sentiment_analysis", state),
    )
    return {
        "topics": topics_res,
        "highlights": highlights_res,
        "speakers": speakers_res,
        "sentiment": sentiment_res,
    }
