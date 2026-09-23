from __future__ import annotations

import array
from pathlib import Path

import pytest
from app.services.quality import (
    CONFIDENCE_THRESHOLD,
    SILENCE_THRESHOLD,
    evaluate_confidence,
    inspect_media,
)
from pydub import AudioSegment
from pydub.generators import Sine


def _create_wav(
    path: Path,
    tone_ms: int = 2000,
    silence_ms: int = 0,
    sample_rate: int = 44100,
    frequency: int = 440,
) -> Path:
    """Helper to generate a clean synthetic WAV with specified tone and silence durations."""
    tone = Sine(frequency, sample_rate=sample_rate).to_audio_segment(duration=tone_ms)
    if silence_ms > 0:
        silence = AudioSegment.silent(duration=silence_ms, frame_rate=sample_rate)
        audio = tone + silence
    else:
        audio = tone
    audio.export(str(path), format="wav")
    return path


def _create_clipped_wav(path: Path, duration_ms: int = 2000, sample_rate: int = 44100) -> Path:
    """Helper to generate an audio file with severe digital waveform clipping."""
    tone = Sine(440, sample_rate=sample_rate).to_audio_segment(duration=duration_ms)
    samples = tone.get_array_of_samples()
    # Clamp 80% of samples to integer limits (hard digital clipping)
    max_val = 32767
    min_val = -32768
    clipped = array.array(
        samples.typecode,
        [max_val if s > 5000 else (min_val if s < -5000 else s) for s in samples],
    )
    clipped_audio = tone._spawn(clipped.tobytes())
    clipped_audio.export(str(path), format="wav")
    return path


def test_silence_ratio_below_40_percent_passes(tmp_path: Path) -> None:
    # 3000ms active tone + 500ms silence = ~14.3% silence (< 40% threshold)
    wav_path = _create_wav(tmp_path / "low_silence.wav", tone_ms=3000, silence_ms=500)
    report = inspect_media(str(wav_path))

    assert report.ok is True
    assert report.silence_ratio is not None
    assert report.silence_ratio <= SILENCE_THRESHOLD
    assert report.recommendation == "continue"
    assert report.status == "continue"
    assert report.reason is None
    assert report.duration_sec == pytest.approx(3.5, abs=0.1)


def test_silence_ratio_above_40_percent_needs_reupload(tmp_path: Path) -> None:
    # 1000ms active tone + 2000ms silence = ~66.7% silence (> 40% threshold)
    wav_path = _create_wav(tmp_path / "high_silence.wav", tone_ms=1000, silence_ms=2000)
    report = inspect_media(str(wav_path))

    assert report.ok is False
    assert report.silence_ratio is not None
    assert report.silence_ratio > SILENCE_THRESHOLD
    assert report.recommendation == "needs_reupload"
    assert report.status == "needs_reupload"
    assert "Excessive silence detected" in (report.reason or "")


def test_100_percent_silent_audio_needs_reupload(tmp_path: Path) -> None:
    # Pure silence (no active audio waveform)
    silent_audio = AudioSegment.silent(duration=2000, frame_rate=44100)
    wav_path = tmp_path / "pure_silence.wav"
    silent_audio.export(str(wav_path), format="wav")

    report = inspect_media(str(wav_path))
    assert report.ok is False
    assert report.silence_ratio == 1.0
    assert report.recommendation == "needs_reupload"
    assert report.status == "needs_reupload"


def test_confidence_below_35_needs_reupload(tmp_path: Path) -> None:
    # High quality audio waveform, but downstream/STT confidence is below 0.35
    wav_path = _create_wav(tmp_path / "low_confidence.wav", tone_ms=2500, silence_ms=0)
    report = inspect_media(str(wav_path), confidence=0.30)

    assert report.ok is False
    assert report.confidence == 0.30
    assert report.recommendation == "needs_reupload"
    assert report.status == "needs_reupload"
    assert "below threshold (0.35)" in (report.reason or "")


def test_confidence_at_or_above_35_passes(tmp_path: Path) -> None:
    wav_path = _create_wav(tmp_path / "good_conf.wav", tone_ms=2500, silence_ms=0)

    # Boundary check at exactly 0.35
    report_boundary = inspect_media(str(wav_path), confidence=0.35)
    assert report_boundary.ok is True
    assert report_boundary.confidence == 0.35
    assert report_boundary.recommendation == "continue"

    # Well above threshold
    report_high = inspect_media(str(wav_path), confidence=0.85)
    assert report_high.ok is True
    assert report_high.confidence == 0.85
    assert report_high.recommendation == "continue"


def test_duration_calculation_and_limits(tmp_path: Path) -> None:
    # Standard valid duration
    wav_2500 = _create_wav(tmp_path / "dur_2500.wav", tone_ms=2500, silence_ms=0)
    report = inspect_media(str(wav_2500))
    assert report.duration_sec == pytest.approx(2.5, abs=0.05)

    # Sub-second duration (< 1.0s) must be rejected
    wav_short = _create_wav(tmp_path / "too_short.wav", tone_ms=600, silence_ms=0)
    report_short = inspect_media(str(wav_short))
    assert report_short.ok is False
    assert report_short.recommendation == "needs_reupload"
    assert "too short" in (report_short.reason or "")

    # Empty file (0 bytes)
    empty_path = tmp_path / "empty.wav"
    empty_path.write_bytes(b"")
    report_empty = inspect_media(str(empty_path))
    assert report_empty.ok is False
    assert report_empty.duration_sec == 0.0
    assert report_empty.recommendation == "needs_reupload"
    assert "Empty media file" in (report_empty.reason or "")

    # Non-existent file
    report_missing = inspect_media(str(tmp_path / "does_not_exist.wav"))
    assert report_missing.ok is False
    assert report_missing.recommendation == "needs_reupload"
    assert "not found" in (report_missing.reason or "")


def test_sample_rate_detection(tmp_path: Path) -> None:
    # 16000 Hz sample rate
    wav_16k = _create_wav(tmp_path / "rate_16k.wav", tone_ms=2000, sample_rate=16000)
    report_16k = inspect_media(str(wav_16k))
    assert report_16k.sample_rate == 16000

    # 44100 Hz sample rate
    wav_44k = _create_wav(tmp_path / "rate_44k.wav", tone_ms=2000, sample_rate=44100)
    report_44k = inspect_media(str(wav_44k))
    assert report_44k.sample_rate == 44100


def test_clipping_detection(tmp_path: Path) -> None:
    # Clean sine wave has no clipping
    clean_wav = _create_wav(tmp_path / "clean.wav", tone_ms=2000)
    report_clean = inspect_media(str(clean_wav))
    assert report_clean.is_clipped is False
    assert report_clean.clipping_ratio is not None
    assert report_clean.clipping_ratio < 0.01

    # Severely clipped wave has clipped samples > 15%
    clipped_wav = _create_clipped_wav(tmp_path / "clipped.wav", duration_ms=2000)
    report_clipped = inspect_media(str(clipped_wav))
    assert report_clipped.is_clipped is True
    assert report_clipped.clipping_ratio is not None
    assert report_clipped.clipping_ratio > 0.15
    assert report_clipped.ok is False
    assert report_clipped.recommendation == "needs_reupload"
    assert "Severe audio clipping distortion detected" in (report_clipped.reason or "")


def test_corrupt_invalid_media_handling(tmp_path: Path) -> None:
    # Invalid audio binary data
    corrupt_path = tmp_path / "corrupt.wav"
    corrupt_path.write_bytes(b"RIFF\x00\x00\x00\x00INVALIDAUDIOBYTESDATA1234567890")

    report = inspect_media(str(corrupt_path))
    assert report.ok is False
    assert report.recommendation == "needs_reupload"
    assert report.status == "needs_reupload"
    assert "Could not decode audio file" in (report.reason or "")


def test_text_source_handling_regression(tmp_path: Path) -> None:
    # Non-empty transcript file (.txt)
    txt_path = tmp_path / "transcript.txt"
    txt_path.write_text("Hello, this is a valid event transcript text file.", encoding="utf-8")
    report_txt = inspect_media(str(txt_path))
    assert report_txt.ok is True
    assert report_txt.silence_ratio == 0.0
    assert report_txt.recommendation == "continue"
    assert report_txt.status == "continue"

    # Non-empty markdown file (.md)
    md_path = tmp_path / "notes.md"
    md_path.write_text("# Meeting Notes\nDiscussion on architecture.", encoding="utf-8")
    report_md = inspect_media(str(md_path))
    assert report_md.ok is True
    assert report_md.recommendation == "continue"

    # Empty text file
    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_text("   \n\t  ", encoding="utf-8")
    report_empty = inspect_media(str(empty_txt))
    assert report_empty.ok is False
    assert report_empty.recommendation == "needs_reupload"
    assert report_empty.reason == "Empty transcript file"

    # Text source with low confidence score (< 0.35)
    report_low_conf = inspect_media(str(txt_path), confidence=0.20)
    assert report_low_conf.ok is False
    assert report_low_conf.recommendation == "needs_reupload"
    assert "below threshold" in (report_low_conf.reason or "")


def test_evaluate_confidence_helper() -> None:
    ok, reason = evaluate_confidence(None)
    assert ok is True
    assert reason is None

    ok, reason = evaluate_confidence(0.85)
    assert ok is True
    assert reason is None

    ok, reason = evaluate_confidence(0.35)
    assert ok is True
    assert reason is None

    ok, reason = evaluate_confidence(0.34)
    assert ok is False
    assert reason is not None
    assert f"below threshold ({CONFIDENCE_THRESHOLD})" in reason


def test_quality_report_as_dict_contract(tmp_path: Path) -> None:
    wav_path = _create_wav(tmp_path / "dict_test.wav", tone_ms=2000, silence_ms=0)
    report = inspect_media(str(wav_path), confidence=0.88)
    data = report.as_dict()

    expected_keys = {
        "duration_sec",
        "sample_rate",
        "silence_ratio",
        "clipping_ratio",
        "is_clipped",
        "confidence",
        "ok",
        "status",
        "reason",
        "recommendation",
    }
    assert set(data.keys()) == expected_keys
    assert data["ok"] is True
    assert data["status"] == "continue"
    assert data["recommendation"] == "continue"
    assert data["confidence"] == 0.88
    assert data["sample_rate"] == 44100
    assert data["duration_sec"] == pytest.approx(2.0, abs=0.05)
