from __future__ import annotations

import asyncio
import io
from pathlib import Path

import structlog

from app.core.config import get_settings
from app.providers.gemini_stt import _MEDIA_MIME
from app.providers.stt import STTProvider, TranscriptResult, TranscriptSegment

logger = structlog.get_logger("vertex_stt")

PROMPT = (
    "Transcribe the following audio recording accurately and completely. "
    "Return only the spoken transcript text without any markdown commentary or prefixes."
)
INLINE_LIMIT = 19 * 1024 * 1024  # Vertex AI inline request data limit is ~20 MB
SEARCH_MS = 10_000  # look this far back from a window end for a quiet split point
FRAME_MS = 250


def _split_points(audio, window_ms: int) -> list[int]:
    """Window ends moved back to the quietest 250 ms frame within the last 10 s,
    so chunk boundaries fall between words rather than inside them."""
    points, start, total = [], 0, len(audio)
    while total - start > window_ms:
        end = start + window_ms
        best, best_db = end, float("inf")
        for pos in range(end - SEARCH_MS, end - FRAME_MS + 1, FRAME_MS):
            db = audio[pos : pos + FRAME_MS].dBFS
            if db < best_db:
                best, best_db = pos + FRAME_MS // 2, db
        points.append(best)
        start = best
    return points


def _chunks(path: str, window_sec: int) -> list[tuple[bytes, str, float, float]]:
    """(data, mime, start_sec, end_sec) per chunk. 16 kHz mono WAV windows when the
    audio can be decoded locally (WAV always; other formats need ffmpeg), otherwise
    the whole file inline if it is small enough."""
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(path).set_channels(1).set_frame_rate(16000)
    except Exception:
        size = Path(path).stat().st_size
        mime = _MEDIA_MIME.get(Path(path).suffix.lower())
        if mime and size <= INLINE_LIMIT:
            return [(Path(path).read_bytes(), mime, 0.0, 0.0)]
        raise RuntimeError("Cannot decode audio locally (install ffmpeg) and file is too large to send inline")

    bounds = [0, *_split_points(audio, window_sec * 1000), len(audio)]
    out = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        buf = io.BytesIO()
        audio[a:b].export(buf, format="wav")
        out.append((buf.getvalue(), "audio/wav", a / 1000, b / 1000))
    return out


class VertexSTTProvider(STTProvider):
    """Gemini speech-to-text on Vertex AI (Application Default Credentials, no API key).
    Long recordings are split at quiet points and the chunks transcribed concurrently."""

    name = "vertex-stt"

    async def transcribe(self, file_path: str) -> TranscriptResult:
        from google.genai import types

        from app.providers.vertex_llm import _client

        settings = get_settings()
        model = settings.vertex_stt_model or settings.gemini_model_analyze
        chunks = await asyncio.to_thread(_chunks, file_path, settings.stt_chunk_seconds)
        client = _client()
        gate = asyncio.Semaphore(settings.stt_concurrency)

        async def _one(data: bytes, mime: str) -> str:
            async with gate:
                # A stalled connection must fail the chunk (and let the runner fall back)
                # instead of hanging the job.
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model,
                        contents=[PROMPT, types.Part.from_bytes(data=data, mime_type=mime)],
                        config=types.GenerateContentConfig(temperature=0.0),
                    ),
                    timeout=settings.stt_chunk_timeout_seconds,
                )
                return (response.text or "").strip()

        texts = await asyncio.gather(*(_one(data, mime) for data, mime, _, _ in chunks))
        text = " ".join(t for t in texts if t) or "No audible speech detected."
        logger.info("vertex_stt_done", model=model, chunks=len(chunks), words=len(text.split()))
        return TranscriptResult(
            text=text,
            language="en",
            avg_confidence=0.95,  # Gemini returns no confidence; same constant as gemini-stt
            provider=self.name,
            vendor_id=f"vertex:{model}",
            segments=[
                TranscriptSegment(text=t[:500], start=start, end=end, confidence=0.95, speaker="speaker")
                for t, (_, _, start, end) in zip(texts, chunks, strict=True)
                if t
            ],
        )
