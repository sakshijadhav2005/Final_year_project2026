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
    """Runs high-speed unified 4-agent intelligence extraction (topics, highlights, speakers, sentiment) in one optimized pass."""
    llm = get_llm_provider()

    async def _call() -> dict[str, Any]:
        prompt = (
            "TASK=multi_agent_intelligence\n"
            "Extract structured intelligence from this event recording. Return JSON with keys:\n"
            "1. 'topics': list of main topics and themes covered (e.g. ['Keynote', 'AI Trends'])\n"
            "2. 'highlights': list of standout takeaways, notable quotes, or milestone points\n"
            "3. 'speakers': list of speaker insights, roles, or speaking styles\n"
            "4. 'sentiment': session tone (e.g. {'tone': 'inspiring and technical', 'energy': 'high'})\n"
        )
        return await llm.generate_json(
            system=analysis_system(),
            user=f"{prompt}\n<untrusted_transcript>\n{state.get('transcript_text', '')}\n</untrusted_transcript>",
            temperature=0.2,
        )

    result = await with_backoff(_call, circuit=llm_circuit)
    
    topics = result.get("topics") if isinstance(result.get("topics"), list) else [result.get("topics", "Event topics")]
    highlights = result.get("highlights") if isinstance(result.get("highlights"), list) else [result.get("highlights", "Key takeaways")]
    speakers = result.get("speakers") if isinstance(result.get("speakers"), list) else [result.get("speakers", "Session speaker")]
    sentiment = result.get("sentiment") if isinstance(result.get("sentiment"), (dict, str)) else {"tone": "engaging"}

    return {
        "topics": {"topics": topics},
        "highlights": {"highlights": highlights},
        "speakers": {"speakers": speakers},
        "sentiment": {"sentiment": sentiment if isinstance(sentiment, dict) else {"tone": sentiment}},
    }
