from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("quality")

SILENCE_THRESHOLD: float = 0.40  # 40% maximum allowable silence ratio
CONFIDENCE_THRESHOLD: float = 0.35  # 0.35 minimum quality/confidence score threshold
CLIPPING_THRESHOLD: float = 0.15  # 15% severe clipping distortion threshold


@dataclass
class QualityReport:
    duration_sec: float | None
    sample_rate: int | None
    silence_ratio: float | None
    ok: bool
    reason: str | None = None
    clipping_ratio: float | None = None
    is_clipped: bool | None = None
    confidence: float | None = None
    recommendation: str | None = None

    @property
    def status(self) -> str:
        if self.recommendation:
            return self.recommendation
        return "continue" if self.ok else "needs_reupload"

    def as_dict(self) -> dict[str, Any]:
        return {
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "silence_ratio": self.silence_ratio,
            "clipping_ratio": self.clipping_ratio,
            "is_clipped": self.is_clipped,
            "confidence": self.confidence,
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "recommendation": self.recommendation,
        }


def evaluate_confidence(confidence: float | None) -> tuple[bool, str | None]:
    """Evaluates whether an audio or STT confidence score meets the 0.35 threshold."""
    if confidence is None:
        return True, None
    if confidence < CONFIDENCE_THRESHOLD:
        return False, (
            f"Confidence score ({confidence:.2f}) below threshold ({CONFIDENCE_THRESHOLD})"
        )
    return True, None


def inspect_media(path: str, confidence: float | None = None) -> QualityReport:
    """Performs pre-flight media quality inspection before downstream STT/LLM processing.

    Validates audio duration, sample rate, waveform silence ratio, clipping, and confidence.
    """
    if not path or not Path(path).exists():
        return QualityReport(
            duration_sec=None,
            sample_rate=None,
            silence_ratio=None,
            ok=False,
            reason=f"Media file not found: {path}",
            clipping_ratio=None,
            is_clipped=None,
            confidence=0.0,
            recommendation="needs_reupload",
        )

    file_path = Path(path)
    if file_path.stat().st_size == 0:
        return QualityReport(
            duration_sec=0.0,
            sample_rate=None,
            silence_ratio=1.0,
            ok=False,
            reason="Empty media file (0 bytes)",
            clipping_ratio=0.0,
            is_clipped=False,
            confidence=0.0,
            recommendation="needs_reupload",
        )

    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return QualityReport(
                duration_sec=None,
                sample_rate=None,
                silence_ratio=None,
                ok=False,
                reason="Empty transcript file",
                clipping_ratio=None,
                is_clipped=False,
                confidence=0.0,
                recommendation="needs_reupload",
            )
        conf_ok, conf_reason = evaluate_confidence(confidence)
        if not conf_ok:
            return QualityReport(
                duration_sec=None,
                sample_rate=None,
                silence_ratio=0.0,
                ok=False,
                reason=conf_reason,
                clipping_ratio=0.0,
                is_clipped=False,
                confidence=confidence,
                recommendation="needs_reupload",
            )
        return QualityReport(
            duration_sec=None,
            sample_rate=None,
            silence_ratio=0.0,
            ok=True,
            reason="Text source; audio quality N/A",
            clipping_ratio=0.0,
            is_clipped=False,
            confidence=confidence if confidence is not None else 1.0,
            recommendation="continue",
        )

    settings = get_settings()

    try:
        from pydub import AudioSegment
        from pydub.silence import detect_silence

        audio = AudioSegment.from_file(path)
        duration = round(len(audio) / 1000.0, 3)
        sample_rate = audio.frame_rate

        # 1. Duration check
        if duration < 1.0:
            return QualityReport(
                duration_sec=duration,
                sample_rate=sample_rate,
                silence_ratio=1.0,
                ok=False,
                reason="Recording is too short (< 1 second)",
                clipping_ratio=0.0,
                is_clipped=False,
                confidence=0.0,
                recommendation="needs_reupload",
            )

        if duration > settings.max_duration_sec:
            return QualityReport(
                duration_sec=duration,
                sample_rate=sample_rate,
                silence_ratio=0.0,
                ok=False,
                reason=f"Recording exceeds {settings.max_duration_sec} seconds",
                clipping_ratio=0.0,
                is_clipped=False,
                confidence=0.0,
                recommendation="needs_reupload",
            )

        # 2. Silence ratio analysis
        if audio.dBFS == float("-inf") or audio.max == 0:
            ratio = 1.0
        else:
            silence_thresh = max(-60.0, audio.dBFS - 16.0)
            silences = detect_silence(audio, min_silence_len=400, silence_thresh=silence_thresh)
            silent = sum(end - start for start, end in silences) / 1000.0
            ratio = min(1.0, silent / duration) if duration else 1.0
        ratio = round(ratio, 4)

        # 3. Waveform clipping analysis
        clipping_ratio = 0.0
        is_clipped = False
        try:
            max_amp = audio.max_possible_amplitude
            if max_amp > 0:
                samples = audio.get_array_of_samples()
                total_samples = len(samples)
                if total_samples > 0:
                    step = max(1, total_samples // 50000)
                    sample_slice = samples[::step]
                    clip_thresh = max(1, int(max_amp - 1))
                    clipped_count = sum(1 for s in sample_slice if abs(s) >= clip_thresh)
                    clipping_ratio = round(clipped_count / len(sample_slice), 4)
                    is_clipped = clipping_ratio > 0.01
        except Exception:
            clipping_ratio = 0.0
            is_clipped = False

        # 4. Confidence evaluation
        if confidence is not None:
            eff_confidence = round(confidence, 3)
        else:
            est_conf = 1.0 - (ratio * 1.5) - (clipping_ratio * 2.5)
            if sample_rate < 16000:
                est_conf -= 0.1
            eff_confidence = max(0.0, min(1.0, round(est_conf, 3)))

        # Gate A: Silence ratio exceeds 40% (0.40)
        if ratio > SILENCE_THRESHOLD:
            return QualityReport(
                duration_sec=duration,
                sample_rate=sample_rate,
                silence_ratio=ratio,
                ok=False,
                reason=(
                    f"Excessive silence detected ({ratio * 100:.1f}% > 40%) - "
                    "re-upload a clearer recording"
                ),
                clipping_ratio=clipping_ratio,
                is_clipped=is_clipped,
                confidence=eff_confidence,
                recommendation="needs_reupload",
            )

        # Gate B: Severe clipping distortion exceeds 15% (0.15)
        if clipping_ratio > CLIPPING_THRESHOLD:
            return QualityReport(
                duration_sec=duration,
                sample_rate=sample_rate,
                silence_ratio=ratio,
                ok=False,
                reason=(
                    f"Severe audio clipping distortion detected ({clipping_ratio * 100:.1f}%) - "
                    "re-upload a clearer recording"
                ),
                clipping_ratio=clipping_ratio,
                is_clipped=is_clipped,
                confidence=eff_confidence,
                recommendation="needs_reupload",
            )

        # Gate C: Confidence below 0.35
        if eff_confidence < CONFIDENCE_THRESHOLD:
            return QualityReport(
                duration_sec=duration,
                sample_rate=sample_rate,
                silence_ratio=ratio,
                ok=False,
                reason=(
                    f"Audio quality confidence score ({eff_confidence:.2f}) below threshold "
                    f"({CONFIDENCE_THRESHOLD}) - needs reupload"
                ),
                clipping_ratio=clipping_ratio,
                is_clipped=is_clipped,
                confidence=eff_confidence,
                recommendation="needs_reupload",
            )

        # Passed all pre-flight quality checks
        return QualityReport(
            duration_sec=duration,
            sample_rate=sample_rate,
            silence_ratio=ratio,
            ok=True,
            reason=None,
            clipping_ratio=clipping_ratio,
            is_clipped=is_clipped,
            confidence=eff_confidence,
            recommendation="continue",
        )

    except Exception as exc:
        logger.warning("audio_probe_failed", path=path, error=str(exc))
        return QualityReport(
            duration_sec=None,
            sample_rate=None,
            silence_ratio=None,
            ok=False,
            reason=f"Could not decode audio file: {exc}",
            clipping_ratio=None,
            is_clipped=None,
            confidence=0.0,
            recommendation="needs_reupload",
        )
