from pathlib import Path

from app.providers.factory import get_stt_provider
from app.providers.stt import STTProvider, TranscriptResult, TranscriptSegment
from app.services.resilience import stt_circuit, with_backoff

LOW_CONFIDENCE = 0.55


def denoise_file(path: str) -> str | None:
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(path)
        filtered = audio.high_pass_filter(80).low_pass_filter(8000)
        dest = Path(path).with_name(f"{Path(path).stem}.denoised.wav")
        filtered.export(dest, format="wav")
        return str(dest)
    except Exception:
        return None


def _from_plain_text(path: str) -> TranscriptResult:
    text = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    return TranscriptResult(
        text=text,
        language="en",
        avg_confidence=0.99,
        provider="plaintext",
        vendor_id="local-text",
        segments=[TranscriptSegment(text=text[:500], start=0, end=0, confidence=0.99)],
    )


async def transcribe_file(
    path: str,
    provider: STTProvider | None = None,
) -> TranscriptResult:
    suffix = Path(path).suffix.lower()
    if suffix in {".txt", ".md"}:
        return _from_plain_text(path)

    active_provider = provider or get_stt_provider()

    async def _run(target: str) -> TranscriptResult:
        return await with_backoff(lambda: active_provider.transcribe(target), circuit=stt_circuit)

    result = await _run(path)
    avg = result.avg_confidence
    if avg is not None and avg < LOW_CONFIDENCE:
        cleaned = denoise_file(path)
        if cleaned:
            retry = await _run(cleaned)
            retry.provider = f"{retry.provider}+denoise"
            return retry
    return result
