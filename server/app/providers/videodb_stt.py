"""VideoDB STT provider adapter.

Integrates VideoDB Cloud Speech-to-Text with speaker diarization,
word/segment timestamps, structured confidence scores, and optional scene indexing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from app.core.config import get_settings
from app.providers.stt import STTProvider, TranscriptResult, TranscriptSegment
from app.services.videodb import (
    VideoDBClient,
    VideoDBConfigurationError,
    VideoDBError,
    VideoDBResponseError,
    VideoDBTranscriptionError,
    VideoDBUploadError,
)

logger = structlog.get_logger("videodb_stt")

# Re-export exceptions for consumer convenience
__all__ = [
    "VideoDBError",
    "VideoDBConfigurationError",
    "VideoDBUploadError",
    "VideoDBTranscriptionError",
    "VideoDBResponseError",
    "VideoDBSTTProvider",
    "extract_segments_from_payload",
]


def extract_segments_from_payload(raw: Any) -> list[TranscriptSegment]:
    """Parses raw VideoDB transcript payloads into structured TranscriptSegments.

    Preserves start/end timestamps, speaker tags, and confidence scores when provided.
    Does not invent speaker information if the provider does not return it.
    """
    segments: list[TranscriptSegment] = []
    if raw is None:
        return segments

    items = raw
    if isinstance(raw, dict):
        items = (
            raw.get("segments")
            or raw.get("word_chunks")
            or raw.get("words")
            or raw.get("chunks")
            or raw.get("timeline")
            or raw.get("data")
            or []
        )

    if not isinstance(items, list):
        return segments

    for item in items:
        if not isinstance(item, dict):
            continue

        text = str(
            item.get("text")
            or item.get("word")
            or item.get("transcript")
            or item.get("content")
            or ""
        ).strip()
        if not text:
            continue

        # Timestamps
        try:
            start_val = item.get("start") or item.get("start_time") or item.get("start_sec") or 0.0
            start = round(float(start_val), 3)
        except (TypeError, ValueError):
            start = 0.0

        try:
            end_val = item.get("end") or item.get("end_time") or item.get("end_sec") or start
            end = round(float(end_val), 3)
        except (TypeError, ValueError):
            end = start

        # Confidence
        conf_val = item.get("confidence") or item.get("score")
        try:
            confidence = round(float(conf_val), 4) if conf_val is not None else None
        except (TypeError, ValueError):
            confidence = None

        # Speaker information (preserve if present, do NOT invent)
        speaker_raw = (
            item.get("speaker")
            or item.get("speaker_id")
            or item.get("speaker_name")
            or item.get("speaker_tag")
        )
        speaker_str = str(speaker_raw).strip() if speaker_raw is not None else ""
        speaker = speaker_str if speaker_str else None

        segments.append(
            TranscriptSegment(
                text=text,
                start=start,
                end=end,
                confidence=confidence,
                speaker=speaker,
            )
        )

    return segments


def _transcribe_sync(
    file_path: str,
    client: VideoDBClient,
    index_scenes: bool,
) -> TranscriptResult:
    """Synchronous worker function that executes VideoDB media upload and STT."""
    conn = client.connect()
    collection = client.get_collection(conn)
    media = client.upload_media(file_path=file_path, collection=collection)
    vendor_id = str(getattr(media, "id", "") or "")

    # Trigger transcript generation
    client.generate_transcript(media, language_code="en")

    # Optional Scene Indexing
    scenes: list[dict[str, Any]] = []
    if index_scenes:
        scenes = client.index_scenes(media)
    elif hasattr(media, "get_scenes"):
        # If scenes were already indexed or available on the media object
        try:
            raw_scenes = media.get_scenes()
            if isinstance(raw_scenes, list):
                scenes = [s for s in raw_scenes if isinstance(s, dict)]
        except Exception:
            pass

    # Retrieve transcript
    text, raw_payload = client.get_transcript(media)
    segments = extract_segments_from_payload(raw_payload)

    if not text and segments:
        text = " ".join(seg.text for seg in segments)

    if not text:
        raise VideoDBTranscriptionError("VideoDB returned an empty transcript")

    confidences = [s.confidence for s in segments if s.confidence is not None]
    avg = round(sum(confidences) / len(confidences), 4) if confidences else None

    if not segments:
        segments = [TranscriptSegment(text=text[:500], start=0.0, end=0.0, confidence=avg)]

    return TranscriptResult(
        text=text,
        language="en",
        segments=segments,
        avg_confidence=avg,
        provider="videodb",
        vendor_id=vendor_id or None,
        scenes=scenes,
    )


class VideoDBSTTProvider(STTProvider):
    """Speech-to-text provider backed by VideoDB Cloud API."""

    name = "videodb"

    def __init__(
        self,
        api_key: str | None = None,
        collection: str | None = None,
        index_scenes: bool | None = None,
        client: VideoDBClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.collection = collection
        self.index_scenes = (
            index_scenes
            if index_scenes is not None
            else get_settings().videodb_index_scenes
        )
        self.client = client or VideoDBClient(api_key=api_key, collection=collection)

    async def transcribe(self, file_path: str) -> TranscriptResult:
        """Asynchronously transcribes an audio or video file via VideoDB."""
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        return await asyncio.to_thread(
            _transcribe_sync,
            str(path_obj),
            self.client,
            self.index_scenes,
        )
