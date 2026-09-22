from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass
class QualityReport:
    duration_sec: float | None
    sample_rate: int | None
    silence_ratio: float | None
    ok: bool
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "silence_ratio": self.silence_ratio,
            "ok": self.ok,
            "reason": self.reason,
        }


def inspect_media(path: str) -> QualityReport:
    suffix = Path(path).suffix.lower()
    if suffix in {".txt", ".md"}:
        text = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return QualityReport(None, None, None, False, "Empty transcript file")
        return QualityReport(None, None, 0.0, True, "Text source; audio quality N/A")

    settings = get_settings()
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_silence

        audio = AudioSegment.from_file(path)
        duration = len(audio) / 1000.0
        silences = detect_silence(audio, min_silence_len=400, silence_thresh=audio.dBFS - 16)
        silent = sum(end - start for start, end in silences) / 1000.0
        ratio = silent / duration if duration else 1.0
        if duration < 1:
            return QualityReport(duration, audio.frame_rate, ratio, False, "Recording is too short")
        if duration > settings.max_duration_sec:
            return QualityReport(
                duration,
                audio.frame_rate,
                ratio,
                False,
                f"Recording exceeds {settings.max_duration_sec} seconds",
            )
        if ratio > 0.92:
            return QualityReport(
                duration, audio.frame_rate, ratio, False, "Mostly silence — re-upload a clearer recording"
            )
        return QualityReport(duration, audio.frame_rate, ratio, True, None)
    except Exception:
        return QualityReport(None, None, None, True, "Could not probe audio locally; continuing with transcription")
