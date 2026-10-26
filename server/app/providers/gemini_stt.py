from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.providers.stt import STTProvider, TranscriptResult, TranscriptSegment

# Audio formats Gemini reads directly, with the MIME type to declare on upload.
_GEMINI_AUDIO_MIME = {
    ".mp3": "audio/mp3",
    ".m4a": "audio/aac",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
}
_MEDIA_MIME = {
    **_GEMINI_AUDIO_MIME,
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".weba": "audio/webm",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".3gp": "video/3gpp",
}


def _mime_for(path: str) -> str | None:
    from pathlib import Path

    return _MEDIA_MIME.get(Path(path).suffix.lower())


def _compact_audio(file_path: str) -> str:
    """Extract a 16 kHz mono MP3 for speech-to-text (needs ffmpeg). Falls back to the
    original file if extraction is not possible."""
    from pathlib import Path

    src = Path(file_path)
    if (
        src.suffix.lower() in _GEMINI_AUDIO_MIME
        and src.suffix.lower() != ".wav"
        and src.stat().st_size < 25 * 1024 * 1024
    ):
        return file_path
    try:
        from pydub import AudioSegment

        dest = src.with_name(f"{src.stem}.stt.mp3")
        audio = AudioSegment.from_file(file_path).set_channels(1).set_frame_rate(16000)
        audio.export(dest, format="mp3", bitrate="48k")
        return str(dest)
    except Exception:
        return file_path


class GeminiSTTProvider(STTProvider):
    """Transcribes audio/video directly using Google Gemini Multimodal capabilities."""

    name = "gemini-stt"

    async def transcribe(self, file_path: str) -> TranscriptResult:
        settings = get_settings()
        import google.generativeai as genai

        def _sync_transcribe() -> str:
            import time

            genai.configure(api_key=settings.gemini_api_key)
            # Upload a small mono speech track instead of the full video (often 10-50x smaller).
            upload_path = _compact_audio(file_path)
            audio_file = genai.upload_file(path=upload_path, mime_type=_mime_for(upload_path))
            # Large files are processed asynchronously by Gemini; asking for a transcript
            # before the file is ACTIVE fails and used to trigger a full re-upload.
            deadline = time.monotonic() + 300
            while getattr(getattr(audio_file, "state", None), "name", "ACTIVE") == "PROCESSING":
                if time.monotonic() > deadline:
                    raise TimeoutError("Gemini is still processing the uploaded audio")
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)

            valid_models = list(
                dict.fromkeys(
                    m
                    for m in (
                        settings.gemini_model_analyze,
                        "gemini-3.6-flash",
                        "gemini-3.7-flash",
                        "gemini-flash-latest",
                    )
                    if m
                )
            )

            last_err = None
            for model_name in valid_models:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content([
                        "Transcribe the following audio/video recording accurately and completely. "
                        "Return only the spoken transcript text without any markdown commentary or prefixes.",
                        audio_file,
                    ])
                    if response and response.text:
                        return response.text.strip()
                except Exception as exc:
                    last_err = exc
                    continue

            if last_err:
                raise last_err
            return ""

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _sync_transcribe)

        if not text:
            text = "No audible speech detected."

        return TranscriptResult(
            text=text,
            language="en",
            avg_confidence=0.95,
            provider=self.name,
            vendor_id="gemini-audio",
            segments=[
                TranscriptSegment(
                    text=text[:500],
                    start=0.0,
                    end=0.0,
                    confidence=0.95,
                    speaker="speaker",
                )
            ],
        )
