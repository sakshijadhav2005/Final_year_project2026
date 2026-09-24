from pathlib import Path

from app.providers.factory import get_stt_provider
from app.providers.stt import TranscriptResult, TranscriptSegment
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


def is_mostly_silent(path: str) -> bool:
    """Uses Voice Activity Detection to determine if the audio is just background noise/silence."""
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent
        
        audio = AudioSegment.from_file(path)
        # If absolute volume is incredibly low, it's silence
        if audio.dBFS < -45:
            return True
            
        # Detect actual speech blocks (louder than -35dB)
        nonsilent_ranges = detect_nonsilent(audio, min_silence_len=300, silence_thresh=-35)
        total_nonsilent = sum(end - start for start, end in nonsilent_ranges)
        
        # If there is less than 0.5 seconds of total speech, it's basically silent/coughing
        return total_nonsilent < 500
    except Exception:
        return False


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


async def transcribe_file(path: str) -> TranscriptResult:
    suffix = Path(path).suffix.lower()
    if suffix in {".txt", ".md"}:
        return _from_plain_text(path)

    # VAD Pre-Check: Stop Whisper Hallucinations before they happen
    if is_mostly_silent(path):
        return TranscriptResult(
            text="[NOISY_DATA_ALERT] Audio contains no detectable speech.",
            language="en",
            avg_confidence=0.0,
            provider="vad_precheck",
            vendor_id="local",
            segments=[]
        )

    provider = get_stt_provider()

    async def _run(target: str) -> TranscriptResult:
        return await with_backoff(lambda: provider.transcribe(target), circuit=stt_circuit)

    result = await _run(path)
    avg = result.avg_confidence
    if avg is not None and avg < LOW_CONFIDENCE:
        cleaned = denoise_file(path)
        if cleaned:
            retry = await _run(cleaned)
            retry.provider = f"{retry.provider}+denoise"
            return retry
    return result
