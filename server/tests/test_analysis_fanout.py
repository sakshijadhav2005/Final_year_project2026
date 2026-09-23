"""Comprehensive tests for Task 5: LangGraph state and parallel fan-out analysis pipeline."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import patch

import pytest
from app.graphs.nodes.analysis import (
    analyze_sentiment,
    analyze_speakers,
    detect_highlights,
    extract_topics,
    highlight_detection,
    parallel_analysis,
    sentiment_analysis,
    speaker_analysis,
    topic_extraction,
)
from app.graphs.nodes.quality import quality_check
from app.graphs.pipeline import _after_quality, get_compiled_graph
from app.graphs.state import JobGraphState


@pytest.fixture
def sample_segments() -> list[dict[str, Any]]:
    return [
        {
            "text": "Welcome to our annual AI and developer summit.",
            "start": 0.0,
            "end": 4.5,
            "speaker": "Speaker 1",
            "confidence": 0.95,
        },
        {
            "text": "Today we are discussing real-time streaming and LangGraph workflows.",
            "start": 5.0,
            "end": 10.2,
            "speaker": "Speaker 2",
            "confidence": 0.92,
        },
        {
            "text": "Parallel fan-out execution makes processing fast and scalable.",
            "start": 10.5,
            "end": 15.0,
            "speaker": "Speaker 1",
            "confidence": 0.98,
        },
    ]


@pytest.fixture
def sample_state(sample_segments: list[dict[str, Any]]) -> JobGraphState:
    text = (
        "Welcome to our annual AI and developer summit. "
        "Today we are discussing real-time streaming and LangGraph workflows. "
        "Parallel fan-out execution makes processing fast and scalable."
    )
    return {
        "job_id": "job-12345",
        "user_id": "user-67890",
        "recording_id": "rec-11111",
        "transcript_text": text,
        "transcript_segments": sample_segments,
        "scenes": [{"start": 0.0, "end": 15.0, "description": "Keynote presentation"}],
        "avg_confidence": 0.95,
        "quality": {"ok": True, "duration_sec": 15.0, "recommendation": "proceed"},
        "requested_types": ["summary", "linkedin"],
        "target_languages": ["en"],
        "use_org_memory": False,
        "user_memory": {"full_name": "Antigravity Engineer"},
        "retry_count": 0,
        "rag_chunks": [],
    }


def test_langgraph_state_initialization(sample_state: JobGraphState) -> None:
    """Requirement 1: Verify typed JobGraphState initialization supports all required keys."""
    assert sample_state["job_id"] == "job-12345"
    assert sample_state["recording_id"] == "rec-11111"
    assert len(sample_state["transcript_segments"]) == 3
    assert sample_state["quality"]["ok"] is True
    assert sample_state["avg_confidence"] == 0.95
    assert sample_state["scenes"][0]["description"] == "Keynote presentation"


@pytest.mark.asyncio
async def test_quality_gate_stops_expensive_analysis(sample_state: JobGraphState) -> None:
    """Requirement 2: If quality check fails, pipeline halts before expensive analysis."""
    # Subcase A: quality explicitly recommends reupload
    bad_quality_state = dict(sample_state)
    bad_quality_state["quality"] = {"ok": False, "recommendation": "needs_reupload"}
    res = await quality_check(bad_quality_state)
    assert res == {"route": "needs_reupload"}
    assert _after_quality(res) == "needs_reupload"

    # Subcase B: quality status is needs_reupload
    bad_status_state = dict(sample_state)
    bad_status_state["quality"] = {"ok": True, "status": "needs_reupload"}
    res = await quality_check(bad_status_state)
    assert res == {"route": "needs_reupload"}
    assert _after_quality(res) == "needs_reupload"

    # Subcase C: low transcription confidence (< 0.35)
    low_conf_state = dict(sample_state)
    low_conf_state["avg_confidence"] = 0.25
    res = await quality_check(low_conf_state)
    assert res == {"route": "needs_reupload"}
    assert _after_quality(res) == "needs_reupload"

    # Subcase D: clean state routes to parallel analysis
    clean_res = await quality_check(sample_state)
    assert clean_res == {"route": "continue"}
    assert _after_quality(clean_res) == "parallel_analysis"


@pytest.mark.asyncio
async def test_transcript_passed_correctly_into_analysis(sample_state: JobGraphState) -> None:
    """Requirement 3: Verify transcript text and segments are passed and utilized."""
    topics = await extract_topics(sample_state)
    assert topics["status"] == "completed"
    assert len(topics["topics"]) > 0

    highlights = await detect_highlights(sample_state)
    assert highlights["status"] == "completed"
    assert highlights["count"] > 0

    speakers = await analyze_speakers(sample_state)
    assert speakers["diarization_available"] is True
    assert "Speaker 1" in speakers["stats"]["turns"]

    sentiment = await analyze_sentiment(sample_state)
    assert sentiment["status"] == "completed"


@pytest.mark.asyncio
async def test_topic_analysis_structured_output(sample_state: JobGraphState) -> None:
    """Requirement 4: Topic extraction returns structured topics, keywords, confidence."""
    result = await extract_topics(sample_state)
    assert result["status"] == "completed"
    assert isinstance(result["topics"], list)
    assert isinstance(result["keywords"], list)
    assert "categories" in result
    assert "confidence" in result
    assert isinstance(result["confidence"], int | float)

    # Single-branch wrapper invocation
    wrapped = await topic_extraction(sample_state)
    assert "topics" in wrapped
    assert wrapped["topics"]["status"] == "completed"


@pytest.mark.asyncio
async def test_highlight_analysis_structured_output(sample_state: JobGraphState) -> None:
    """Requirement 5: Highlight detection preserves quotes, timestamps, and reasons."""
    result = await detect_highlights(sample_state)
    assert result["status"] == "completed"
    assert isinstance(result["highlights"], list)
    assert len(result["highlights"]) > 0
    first = result["highlights"][0]
    assert "quote" in first
    assert "start" in first
    assert "end" in first
    assert "why" in first

    # Single-branch wrapper invocation
    wrapped = await highlight_detection(sample_state)
    assert "highlights" in wrapped
    assert wrapped["highlights"]["status"] == "completed"


@pytest.mark.asyncio
async def test_speaker_analysis_structured_output(sample_state: JobGraphState) -> None:
    """Requirement 6: Speaker analysis calculates turn counts and durations for speakers."""
    result = await analyze_speakers(sample_state)
    assert result["status"] == "completed"
    assert result["diarization_available"] is True
    assert result["speaker_count"] == 2
    assert "Speaker 1" in result["stats"]["turns"]
    assert "Speaker 2" in result["stats"]["turns"]
    assert result["stats"]["turns"]["Speaker 1"] == 2
    assert result["stats"]["turns"]["Speaker 2"] == 1
    assert result["stats"]["durations_sec"]["Speaker 1"] > 0.0

    # Single-branch wrapper invocation
    wrapped = await speaker_analysis(sample_state)
    assert "speakers" in wrapped
    assert wrapped["speakers"]["status"] == "completed"


@pytest.mark.asyncio
async def test_speaker_analysis_no_invented_speakers_when_missing(
    sample_state: JobGraphState,
) -> None:
    """Requirement 12: Do NOT invent synthetic speaker data if speaker information is missing."""
    state_no_speakers = dict(sample_state)
    state_no_speakers["transcript_segments"] = [
        {"text": "A segment without speaker.", "start": 0.0, "end": 2.0},
        {"text": "Another segment without speaker.", "start": 2.5, "end": 5.0, "speaker": None},
    ]

    result = await analyze_speakers(state_no_speakers)
    assert result["diarization_available"] is False
    assert result["speaker_count"] == 0
    assert result["speakers"] == []
    assert result["status"] == "no_speaker_data"
    assert "No speaker diarization data available" in result["notes"]


@pytest.mark.asyncio
async def test_sentiment_analysis_structured_output(sample_state: JobGraphState) -> None:
    """Requirement 7: Sentiment analysis produces structured overall and score assessment."""
    result = await analyze_sentiment(sample_state)
    assert result["status"] == "completed"
    assert result["overall"] in {"positive", "neutral", "negative"}
    assert isinstance(result["score"], int | float)
    assert 0.0 <= result["score"] <= 1.0

    # Single-branch wrapper invocation
    wrapped = await sentiment_analysis(sample_state)
    assert "sentiment" in wrapped
    assert wrapped["sentiment"]["status"] == "completed"


@pytest.mark.asyncio
async def test_parallel_execution_concurrency(sample_state: JobGraphState) -> None:
    """Requirement 8: Verify that 4 analysis branches execute concurrently."""
    active_tasks = 0
    max_concurrent = 0
    lock = asyncio.Lock()

    from app.graphs.nodes import analysis as analysis_module

    original_agent = analysis_module._agent

    async def mock_agent_with_delay(
        task: str,
        state: JobGraphState,
        extra: str = "",
        temperature: float = 0.2,
    ):
        nonlocal active_tasks, max_concurrent
        async with lock:
            active_tasks += 1
            if active_tasks > max_concurrent:
                max_concurrent = active_tasks
        try:
            # Simulate a 50ms asynchronous I/O delay in each branch
            await asyncio.sleep(0.05)
            return await original_agent(task, state, extra=extra, temperature=temperature)
        finally:
            async with lock:
                active_tasks -= 1

    start_time = time.monotonic()
    with patch.object(analysis_module, "_agent", side_effect=mock_agent_with_delay):
        res = await parallel_analysis(sample_state)
    elapsed = time.monotonic() - start_time

    assert res["analysis_status"] == "completed"
    # Concurrency verification:
    # 1. At least 2 tasks (up to 4) ran concurrently at the same time
    assert max_concurrent >= 2, f"Expected concurrency >= 2, got {max_concurrent}"
    # 2. Sequential execution of 4 x 50ms would take >= 0.20s; parallel should complete in << 0.20s
    assert elapsed < 0.18, f"Execution took {elapsed:.2f}s, indicating sequential execution"


@pytest.mark.asyncio
async def test_fan_in_combined_result(sample_state: JobGraphState) -> None:
    """Requirement 9: Combine results into combined_analysis state."""
    result = await parallel_analysis(sample_state)

    # Check top-level fan-in keys
    assert "topics" in result
    assert "highlights" in result
    assert "speakers" in result
    assert "sentiment" in result
    assert "analysis_errors" in result
    assert "analysis_status" in result
    assert "combined_analysis" in result

    comb = result["combined_analysis"]
    assert comb["status"] == "completed"
    assert comb["errors"] == {}
    assert comb["topics"]["status"] == "completed"
    assert comb["highlights"]["status"] == "completed"
    assert comb["speakers"]["status"] == "completed"
    assert comb["sentiment"]["status"] == "completed"


@pytest.mark.asyncio
async def test_failure_isolation_one_branch_fails_others_succeed(
    sample_state: JobGraphState,
) -> None:
    """Requirement 10: One failing branch preserves others without failing pipeline."""
    from app.graphs.nodes import analysis as analysis_module

    async def mock_failing_speakers(state: JobGraphState):
        raise RuntimeError("Speaker diarization cluster disconnected")

    with patch.object(analysis_module, "analyze_speakers", side_effect=mock_failing_speakers):
        result = await parallel_analysis(sample_state)

    # Speakers failed
    assert result["speakers"]["status"] == "failed"
    assert "Speaker diarization cluster disconnected" in result["speakers"]["error"]
    assert result["analysis_errors"]["speakers"] == "Speaker diarization cluster disconnected"
    assert result["analysis_status"] == "partial_failure"

    # Other 3 branches succeeded intact
    assert result["topics"]["status"] == "completed"
    assert result["highlights"]["status"] == "completed"
    assert result["sentiment"]["status"] == "completed"

    # Combined analysis reflects partial failure and preserves available results
    comb = result["combined_analysis"]
    assert comb["status"] == "partial_failure"
    assert "speakers" in comb["errors"]
    assert comb["topics"]["status"] == "completed"
    assert comb["highlights"]["status"] == "completed"
    assert comb["sentiment"]["status"] == "completed"


@pytest.mark.asyncio
async def test_empty_transcript_handling() -> None:
    """Requirement 11: Handle empty or whitespace-only transcript safely without crashing."""
    empty_state: JobGraphState = {
        "job_id": "job-empty",
        "transcript_text": "   ",
        "transcript_segments": [],
        "quality": {"ok": True},
    }

    result = await parallel_analysis(empty_state)
    assert result["analysis_status"] == "completed"
    assert result["analysis_errors"] == {}
    assert result["topics"]["status"] == "empty_transcript"
    assert result["highlights"]["status"] == "empty_transcript"
    assert result["sentiment"]["status"] == "empty_transcript"
    assert result["speakers"]["status"] == "no_speaker_data"


@pytest.mark.asyncio
async def test_missing_timestamp_data(sample_state: JobGraphState) -> None:
    """Requirement 13: Handle missing timestamp data gracefully."""
    no_timestamp_state = dict(sample_state)
    no_timestamp_state["transcript_segments"] = [
        {"text": "Segment with no timestamps", "speaker": "Speaker 1"},
        {"text": "Another timestamp-less segment", "speaker": "Speaker 1"},
    ]

    highlights = await detect_highlights(no_timestamp_state)
    assert highlights["status"] == "completed"
    for h in highlights["highlights"]:
        # If timestamp is missing, start/end are None rather than crashing
        assert h.get("start") is None or isinstance(h.get("start"), float)

    speakers = await analyze_speakers(no_timestamp_state)
    assert speakers["status"] == "completed"
    assert speakers["diarization_available"] is True
    assert speakers["stats"]["turns"]["Speaker 1"] == 2
    # Durations default gracefully to 0.0 without errors
    assert speakers["stats"]["durations_sec"]["Speaker 1"] == 0.0


@pytest.mark.asyncio
async def test_full_pipeline_integration(sample_state: JobGraphState) -> None:
    """Requirement 14: Verify full LangGraph pipeline execution with fan-out analysis."""
    graph = get_compiled_graph()
    final_state = await graph.ainvoke(sample_state)

    # Verify quality gate passed
    assert final_state.get("route") == "continue"

    # Verify parallel analysis fan-out ran and combined into final state
    assert "topics" in final_state
    assert final_state["topics"]["status"] == "completed"
    assert "highlights" in final_state
    assert final_state["highlights"]["status"] == "completed"
    assert "speakers" in final_state
    assert final_state["speakers"]["status"] == "completed"
    assert "sentiment" in final_state
    assert final_state["sentiment"]["status"] == "completed"
    assert "combined_analysis" in final_state
    assert final_state["combined_analysis"]["status"] == "completed"

    # Verify downstream nodes received and processed analysis outputs
    assert "brief" in final_state
    assert "generated" in final_state
    assert len(final_state["generated"]) > 0
    assert "guardrail" in final_state
    assert final_state["guardrail"]["pass"] is True


@pytest.mark.asyncio
async def test_full_pipeline_quality_stop_at_end() -> None:
    """Verify quality failure terminates at END without running analysis."""
    bad_state: JobGraphState = {
        "job_id": "job-bad-quality",
        "transcript_text": "Short low confidence.",
        "avg_confidence": 0.1,
        "quality": {"ok": False, "recommendation": "needs_reupload"},
    }

    graph = get_compiled_graph()
    final_state = await graph.ainvoke(bad_state)

    # Route is needs_reupload
    assert final_state.get("route") == "needs_reupload"
    # Expensive analysis was NOT run
    assert "combined_analysis" not in final_state
    assert "topics" not in final_state
    assert "generated" not in final_state
