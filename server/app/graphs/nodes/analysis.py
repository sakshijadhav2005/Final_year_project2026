"""Parallel extraction fan-out nodes: topics, highlights, speakers, sentiment."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.providers.gemini_llm import analysis_system, build_user_prompt
from app.services.resilience import llm_circuit, with_backoff

logger = structlog.get_logger("analysis")


async def _agent(
    task: str,
    state: JobGraphState,
    extra: str = "",
    temperature: float = 0.2,
) -> dict[str, Any]:
    llm = get_llm_provider()
    transcript = state.get("transcript_text", "")

    async def _call() -> dict[str, Any]:
        return await llm.generate_json(
            system=analysis_system(),
            user=build_user_prompt(task, transcript, extra=extra),
            temperature=temperature,
        )

    return await with_backoff(_call, circuit=llm_circuit)


async def fan_out(state: JobGraphState) -> dict[str, Any]:
    """Pass-through node to initiate parallel analysis fan-out."""
    return {"route": state.get("route") or "continue"}


async def extract_topics(state: JobGraphState) -> dict[str, Any]:
    """Branch A: Topic extraction analyzing themes, categories, and keywords."""
    transcript = state.get("transcript_text", "").strip()
    if not transcript:
        return {
            "topics": [],
            "keywords": [],
            "categories": [],
            "session_type": "unknown",
            "status": "empty_transcript",
        }

    raw = await _agent("topic_extraction", state)
    if not isinstance(raw, dict):
        raw = {}
    topics = raw.get("topics") or []
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(",") if t.strip()]

    keywords = raw.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    return {
        "topics": topics,
        "keywords": keywords,
        "categories": raw.get("categories") or raw.get("session_type") or "general",
        "confidence": raw.get("confidence", 0.9),
        "status": "completed",
    }


async def detect_highlights(state: JobGraphState) -> dict[str, Any]:
    """Branch B: Highlight detection preserving start/end timestamps when available."""
    transcript = state.get("transcript_text", "").strip()
    segments = state.get("transcript_segments") or []
    if not transcript:
        return {"highlights": [], "status": "empty_transcript"}

    extra = ""
    if segments:
        seg_snippets = [
            f"[{s.get('start', 0.0)}s - {s.get('end', 0.0)}s] "
            f"{s.get('speaker', 'speaker')}: {s.get('text', '')[:100]}"
            for s in segments[:10]
        ]
        extra = "SEGMENTS_WITH_TIMESTAMPS:\n" + "\n".join(seg_snippets)

    raw = await _agent("highlight_detection", state, extra=extra)
    if not isinstance(raw, dict):
        raw = {}
    items = raw.get("highlights") or []
    if not isinstance(items, list):
        items = [{"quote": str(items), "why": "General session highlight"}]

    clean_highlights: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            quote = item.get("quote") or item.get("text") or ""
            start = item.get("start")
            end = item.get("end")
            why = item.get("why") or item.get("reason") or item.get("importance") or ""
            try:
                start_f = float(start) if start is not None else None
            except (ValueError, TypeError):
                start_f = None
            try:
                end_f = float(end) if end is not None else None
            except (ValueError, TypeError):
                end_f = None
            clean_highlights.append({
                "quote": quote,
                "start": start_f,
                "end": end_f,
                "why": why,
            })
        elif isinstance(item, str):
            clean_highlights.append({
                "quote": item,
                "start": None,
                "end": None,
                "why": "Key takeaway",
            })

    return {
        "highlights": clean_highlights,
        "count": len(clean_highlights),
        "status": "completed",
    }


async def analyze_speakers(state: JobGraphState) -> dict[str, Any]:
    """Branch C: Speaker analysis strictly preserving existing speaker/timestamp data."""
    segments = state.get("transcript_segments") or []
    known_speakers = set()
    speaker_turns: dict[str, int] = {}
    speaker_durations: dict[str, float] = {}

    for s in segments:
        spk = s.get("speaker")
        if spk:
            known_speakers.add(spk)
            speaker_turns[spk] = speaker_turns.get(spk, 0) + 1
            try:
                start = float(s.get("start") or 0.0)
            except (ValueError, TypeError):
                start = 0.0
            try:
                end = float(s.get("end") or start)
            except (ValueError, TypeError):
                end = start
            speaker_durations[spk] = round(
                speaker_durations.get(spk, 0.0) + max(0.0, end - start), 2
            )

    # Strictly enforce: Do NOT invent speaker information if missing
    if not known_speakers:
        return {
            "speakers": [],
            "speaker_count": 0,
            "diarization_available": False,
            "notes": "No speaker diarization data available in transcript.",
            "status": "no_speaker_data",
        }

    extra = (
        f"DETECTED_SPEAKERS: {list(known_speakers)}\n"
        f"SPEAKER_TURNS: {speaker_turns}\n"
        f"SPEAKER_DURATIONS_SEC: {speaker_durations}"
    )
    raw = await _agent("speaker_analysis", state, extra=extra)
    if not isinstance(raw, dict):
        raw = {}

    speakers_list = raw.get("speakers")
    if not isinstance(speakers_list, list):
        speakers_list = [
            {"speaker": spk, "turns": speaker_turns.get(spk, 1)} for spk in known_speakers
        ]

    return {
        "speakers": speakers_list,
        "speaker_count": len(known_speakers),
        "diarization_available": True,
        "stats": {
            "turns": speaker_turns,
            "durations_sec": speaker_durations,
        },
        "notes": raw.get("notes") or "Speaker turns resolved successfully.",
        "status": "completed",
    }


async def analyze_sentiment(state: JobGraphState) -> dict[str, Any]:
    """Branch D: Sentiment analysis producing structured overall and score assessment."""
    transcript = state.get("transcript_text", "").strip()
    if not transcript:
        return {
            "overall": "neutral",
            "score": 0.0,
            "notes": "Empty transcript.",
            "status": "empty_transcript",
        }

    raw = await _agent("sentiment_analysis", state)
    if not isinstance(raw, dict):
        raw = {}
    overall = raw.get("overall") or "neutral"
    confidence = raw.get("confidence") or raw.get("score")
    try:
        score = float(confidence) if confidence is not None else 0.75
    except (TypeError, ValueError):
        score = 0.75

    return {
        "overall": overall,
        "score": score,
        "notes": raw.get("notes") or "",
        "status": "completed",
    }


# Individual single-branch node functions for LangGraph or direct invocation
async def topic_extraction(state: JobGraphState) -> dict[str, Any]:
    return {"topics": await extract_topics(state)}


async def highlight_detection(state: JobGraphState) -> dict[str, Any]:
    return {"highlights": await detect_highlights(state)}


async def speaker_analysis(state: JobGraphState) -> dict[str, Any]:
    return {"speakers": await analyze_speakers(state)}


async def sentiment_analysis(state: JobGraphState) -> dict[str, Any]:
    return {"sentiment": await analyze_sentiment(state)}


async def parallel_analysis(state: JobGraphState) -> dict[str, Any]:
    """Executes all 4 analysis operations concurrently with failure isolation and fan-in."""
    results = await asyncio.gather(
        extract_topics(state),
        detect_highlights(state),
        analyze_speakers(state),
        analyze_sentiment(state),
        return_exceptions=True,
    )

    branch_keys = ["topics", "highlights", "speakers", "sentiment"]
    clean_results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for key, res in zip(branch_keys, results):
        if isinstance(res, Exception):
            logger.error("analysis_branch_failed", branch=key, error=str(res))
            errors[key] = str(res)
            clean_results[key] = {
                "status": "failed",
                "error": str(res),
            }
        elif isinstance(res, dict):
            clean_results[key] = res
        else:
            clean_results[key] = {"value": res, "status": "completed"}

    overall_status = "completed"
    if errors:
        overall_status = "failed" if len(errors) == len(branch_keys) else "partial_failure"

    combined_analysis = {
        "topics": clean_results["topics"],
        "highlights": clean_results["highlights"],
        "speakers": clean_results["speakers"],
        "sentiment": clean_results["sentiment"],
        "errors": errors,
        "status": overall_status,
    }

    return {
        "topics": clean_results["topics"],
        "highlights": clean_results["highlights"],
        "speakers": clean_results["speakers"],
        "sentiment": clean_results["sentiment"],
        "analysis_errors": errors,
        "analysis_status": overall_status,
        "combined_analysis": combined_analysis,
    }
