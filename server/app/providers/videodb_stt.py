"""VideoDB STT adapter. Falls back to documented APIs if the SDK surface differs."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.providers.stt import STTProvider, TranscriptResult, TranscriptSegment


def _segments_from_payload(raw: Any) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    if raw is None:
        return segments
    items = raw
    if isinstance(raw, dict):
        items = raw.get("word_chunks") or raw.get("segments") or raw.get("words") or []
    if not isinstance(items, list):
        return segments
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("word") or "").strip()
        if not text:
            continue
        conf = item.get("confidence") or item.get("score")
        try:
            conf_f = float(conf) if conf is not None else None
        except (TypeError, ValueError):
            conf_f = None
        start = float(item.get("start") or item.get("start_time") or 0)
        end = float(item.get("end") or item.get("end_time") or start)
        segments.append(
            TranscriptSegment(
                text=text,
                start=start,
                end=end,
                confidence=conf_f,
                speaker=item.get("speaker") or item.get("speaker_id"),
            )
        )
    return segments


def _transcribe_sync(file_path: str) -> TranscriptResult:
    import videodb

    settings = get_settings()
    conn = videodb.connect(api_key=settings.videodb_api_key)
    collection = None
    if settings.videodb_collection:
        try:
            collection = conn.get_collection(settings.videodb_collection)
        except TypeError:
            collection = conn.get_collection(collection_id=settings.videodb_collection)
        except Exception:
            collection = conn.get_collection()
    if collection is None:
        collection = conn.get_collection()

    media = collection.upload(file_path=file_path)
    vendor_id = str(getattr(media, "id", "") or "")

    text = ""
    segments: list[TranscriptSegment] = []

    if hasattr(media, "generate_transcript"):
        try:
            media.generate_transcript()
        except TypeError:
            media.generate_transcript(language_code="en")

    if hasattr(media, "get_transcript_text"):
        text = media.get_transcript_text() or ""
    if hasattr(media, "get_transcript"):
        segments = _segments_from_payload(media.get_transcript())
        if not text:
            text = " ".join(seg.text for seg in segments)

    if not text and hasattr(media, "understand"):
        understanding = media.understand(analyzers=[{"type": "spoken_words", "name": "transcript"}])
        if hasattr(understanding, "wait_until_complete"):
            understanding.wait_until_complete()
        analyzer = (
            understanding.get_analyzer("transcript")
            if hasattr(understanding, "get_analyzer")
            else None
        )
        for attr in ("text", "transcript", "content"):
            value = getattr(analyzer, attr, None) if analyzer is not None else None
            if isinstance(value, str) and value.strip():
                text = value
                break
        if not text and analyzer is not None:
            text = str(analyzer)

    if not text:
        raise RuntimeError("VideoDB returned an empty transcript")

    confidences = [s.confidence for s in segments if s.confidence is not None]
    avg = sum(confidences) / len(confidences) if confidences else None
    if not segments:
        segments = [TranscriptSegment(text=text[:500], start=0, end=0, confidence=avg)]
    return TranscriptResult(
        text=text,
        language="en",
        segments=segments,
        avg_confidence=avg,
        provider="videodb",
        vendor_id=vendor_id or None,
    )


class VideoDBSTTProvider(STTProvider):
    name = "videodb"

    async def transcribe(self, file_path: str) -> TranscriptResult:
        return await asyncio.to_thread(_transcribe_sync, file_path)
