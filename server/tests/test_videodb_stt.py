from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import get_settings
from app.providers.factory import get_stt_provider
from app.providers.fake_stt import FakeSTTProvider
from app.providers.stt import TranscriptResult
from app.providers.videodb_stt import (
    VideoDBConfigurationError,
    VideoDBError,
    VideoDBSTTProvider,
    VideoDBTranscriptionError,
    VideoDBUploadError,
    extract_segments_from_payload,
)
from app.services.transcription import transcribe_file


# ---------------------------------------------------------------------------
# 1. FakeSTTProvider Regression
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fake_stt_provider_regression() -> None:
    provider = FakeSTTProvider()
    assert provider.name == "fake"

    result = await provider.transcribe("dummy_file.wav")
    assert isinstance(result, TranscriptResult)
    assert result.provider == "fake"
    assert result.vendor_id == "fake-local"
    assert result.language == "en"
    assert result.avg_confidence == pytest.approx(0.92, abs=0.01)
    assert len(result.segments) >= 2

    seg1 = result.segments[0]
    assert seg1.start == 0.0
    assert seg1.end == 4.2
    assert seg1.speaker == "host"
    assert "EventAI demo" in seg1.text


# ---------------------------------------------------------------------------
# 2. VideoDB Provider Initialization & Configuration
# ---------------------------------------------------------------------------
def test_videodb_provider_initialization() -> None:
    provider = VideoDBSTTProvider(
        api_key="test-api-key",
        collection="test-coll-id",
        index_scenes=True,
    )
    assert provider.name == "videodb"
    assert provider.api_key == "test-api-key"
    assert provider.collection == "test-coll-id"
    assert provider.index_scenes is True


@pytest.mark.asyncio
async def test_videodb_missing_api_key_raises_configuration_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "videodb_api_key", "")
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy audio content")

    provider = VideoDBSTTProvider(api_key="")
    with pytest.raises(VideoDBConfigurationError) as exc_info:
        await provider.transcribe(str(sample_file))
    assert "VideoDB API key is not configured" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. Mocked Successful VideoDB Transcription
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_videodb_mocked_successful_transcription(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy wav data")

    mock_media = MagicMock()
    mock_media.id = "vdb-m-12345"
    mock_media.get_transcript_text.return_value = (
        "Welcome to our final year engineering presentation."
    )
    mock_media.get_transcript.return_value = [
        {
            "text": "Welcome to our final year engineering presentation.",
            "start": 0.5,
            "end": 3.8,
            "confidence": 0.96,
            "speaker": "Sandesh",
        }
    ]

    mock_collection = MagicMock()
    mock_collection.upload.return_value = mock_media

    mock_conn = MagicMock()
    mock_conn.get_collection.return_value = mock_collection

    mock_videodb = MagicMock()
    mock_videodb.connect.return_value = mock_conn

    provider = VideoDBSTTProvider(api_key="fake-vdb-key")

    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        result = await provider.transcribe(str(sample_file))

    assert result.provider == "videodb"
    assert result.vendor_id == "vdb-m-12345"
    assert result.text == "Welcome to our final year engineering presentation."
    assert result.avg_confidence == pytest.approx(0.96, abs=0.01)
    assert len(result.segments) == 1
    assert result.segments[0].speaker == "Sandesh"
    assert result.segments[0].start == 0.5
    assert result.segments[0].end == 3.8


# ---------------------------------------------------------------------------
# 4. Timestamps Preservation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_timestamps_preservation(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy wav data")

    mock_media = MagicMock()
    mock_media.id = "vdb-m-timestamps"
    mock_media.get_transcript_text.return_value = "First segment. Second segment."
    mock_media.get_transcript.return_value = {
        "segments": [
            {"text": "First segment.", "start": 1.234, "end": 5.678, "confidence": 0.91},
            {"text": "Second segment.", "start": 5.678, "end": 9.101, "confidence": 0.88},
        ]
    }

    mock_collection = MagicMock()
    mock_collection.upload.return_value = mock_media
    mock_conn = MagicMock()
    mock_conn.get_collection.return_value = mock_collection
    mock_videodb = MagicMock()
    mock_videodb.connect.return_value = mock_conn

    provider = VideoDBSTTProvider(api_key="fake-vdb-key")

    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        result = await provider.transcribe(str(sample_file))

    assert len(result.segments) == 2
    assert result.segments[0].start == 1.234
    assert result.segments[0].end == 5.678
    assert result.segments[1].start == 5.678
    assert result.segments[1].end == 9.101


# ---------------------------------------------------------------------------
# 5. Speaker Information Preservation (when present vs absent)
# ---------------------------------------------------------------------------
def test_extract_segments_speaker_information() -> None:
    payload = {
        "segments": [
            {
                "text": "Hello, I am speaker one.",
                "start": 0.0,
                "end": 2.0,
                "speaker": "Speaker 1",
            },
            {
                "text": "And I am speaker two with speaker_id tag.",
                "start": 2.0,
                "end": 4.0,
                "speaker_id": "spk_2",
            },
            {
                "text": "I have no speaker information attributed.",
                "start": 4.0,
                "end": 6.0,
            },
        ]
    }
    segments = extract_segments_from_payload(payload)
    assert len(segments) == 3
    assert segments[0].speaker == "Speaker 1"
    assert segments[1].speaker == "spk_2"
    # Must NOT invent speaker information when missing
    assert segments[2].speaker is None


# ---------------------------------------------------------------------------
# 6. Scene Indexing Support
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scene_indexing_when_enabled(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.mp4"
    sample_file.write_bytes(b"dummy video data")

    mock_media = MagicMock()
    mock_media.id = "vdb-m-scenes"
    mock_media.get_transcript_text.return_value = "Video transcript text"
    mock_media.get_transcript.return_value = [
        {"text": "Video transcript text", "start": 0, "end": 5}
    ]
    mock_media.get_scenes.return_value = [
        {"start": 0.0, "end": 2.5, "description": "Opening Title Card"},
        {"start": 2.5, "end": 5.0, "description": "Keynote Speaker Introduction"},
    ]

    mock_collection = MagicMock()
    mock_collection.upload.return_value = mock_media
    mock_conn = MagicMock()
    mock_conn.get_collection.return_value = mock_collection
    mock_videodb = MagicMock()
    mock_videodb.connect.return_value = mock_conn

    provider = VideoDBSTTProvider(api_key="fake-vdb-key", index_scenes=True)

    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        result = await provider.transcribe(str(sample_file))

    assert mock_media.index_scenes.called is True
    assert len(result.scenes) == 2
    assert result.scenes[0]["description"] == "Opening Title Card"
    assert result.scenes[1]["description"] == "Keynote Speaker Introduction"


# ---------------------------------------------------------------------------
# 7. Provider Failure Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_nonexistent_file_raises_filenotfound() -> None:
    provider = VideoDBSTTProvider(api_key="fake-key")
    with pytest.raises(FileNotFoundError):
        await provider.transcribe("non_existent_media_path_123.wav")


@pytest.mark.asyncio
async def test_upload_failure_raises_videodb_upload_error(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy wav data")

    mock_collection = MagicMock()
    mock_collection.upload.side_effect = RuntimeError("Network timeout during upload")
    mock_conn = MagicMock()
    mock_conn.get_collection.return_value = mock_collection
    mock_videodb = MagicMock()
    mock_videodb.connect.return_value = mock_conn

    provider = VideoDBSTTProvider(api_key="fake-key")
    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        with pytest.raises(VideoDBUploadError) as exc_info:
            await provider.transcribe(str(sample_file))
    assert "Failed to upload media to VideoDB" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcription_generation_failure(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy wav data")

    mock_media = MagicMock()
    mock_media.generate_transcript.side_effect = RuntimeError("STT engine unavailable")

    mock_collection = MagicMock()
    mock_collection.upload.return_value = mock_media
    mock_conn = MagicMock()
    mock_conn.get_collection.return_value = mock_collection
    mock_videodb = MagicMock()
    mock_videodb.connect.return_value = mock_conn

    provider = VideoDBSTTProvider(api_key="fake-key")
    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        with pytest.raises(VideoDBTranscriptionError) as exc_info:
            await provider.transcribe(str(sample_file))
    assert "VideoDB generate_transcript failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_connect_failure_raises_videodb_error(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy wav data")

    mock_videodb = MagicMock()
    mock_videodb.connect.side_effect = ConnectionError("Could not reach VideoDB endpoint")

    provider = VideoDBSTTProvider(api_key="fake-key")
    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        with pytest.raises(VideoDBError) as exc_info:
            await provider.transcribe(str(sample_file))
    assert "Failed to connect to VideoDB" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 8. Malformed Response Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_transcript_raises_videodb_transcription_error(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.wav"
    sample_file.write_bytes(b"dummy wav data")

    mock_media = MagicMock()
    mock_media.get_transcript_text.return_value = ""
    mock_media.get_transcript.return_value = None

    mock_collection = MagicMock()
    mock_collection.upload.return_value = mock_media
    mock_conn = MagicMock()
    mock_conn.get_collection.return_value = mock_collection
    mock_videodb = MagicMock()
    mock_videodb.connect.return_value = mock_conn

    provider = VideoDBSTTProvider(api_key="fake-key")
    with patch.dict("sys.modules", {"videodb": mock_videodb}):
        with pytest.raises(VideoDBTranscriptionError) as exc_info:
            await provider.transcribe(str(sample_file))
    assert "empty transcript" in str(exc_info.value)


def test_extract_segments_malformed_payload_graceful() -> None:
    assert extract_segments_from_payload(None) == []
    assert extract_segments_from_payload("some string") == []
    assert extract_segments_from_payload(12345) == []
    assert extract_segments_from_payload({}) == []
    # Dict with non-dict items inside
    raw_mixed = {"segments": ["not a dict", None, {"text": "Valid item", "start": "bad_float"}]}
    segments = extract_segments_from_payload(raw_mixed)
    assert len(segments) == 1
    assert segments[0].text == "Valid item"
    assert segments[0].start == 0.0


# ---------------------------------------------------------------------------
# 9. Provider Factory Selection
# ---------------------------------------------------------------------------
def test_provider_factory_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    # Explicit fake selection
    provider_fake = get_stt_provider("fake")
    assert isinstance(provider_fake, FakeSTTProvider)
    assert provider_fake.name == "fake"

    # Default fallback when no videodb_api_key is set
    monkeypatch.setattr(get_settings(), "videodb_api_key", "")
    provider_default = get_stt_provider()
    assert isinstance(provider_default, FakeSTTProvider)

    # When videodb_api_key is configured
    monkeypatch.setattr(get_settings(), "videodb_api_key", "secret-key-123")
    monkeypatch.setattr(get_settings(), "videodb_collection", "default-coll")
    provider_configured = get_stt_provider()
    assert isinstance(provider_configured, VideoDBSTTProvider)
    assert provider_configured.api_key == "secret-key-123"
    assert provider_configured.collection == "default-coll"


# ---------------------------------------------------------------------------
# 10. Transcription Service Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_transcription_service_plain_text(tmp_path: Path) -> None:
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Plain text transcript bypassing speech-to-text.", encoding="utf-8")

    result = await transcribe_file(str(txt_file))
    assert result.provider == "plaintext"
    assert result.vendor_id == "local-text"
    assert "Plain text transcript" in result.text
    assert result.avg_confidence == 0.99


@pytest.mark.asyncio
async def test_transcription_service_with_fake_provider(tmp_path: Path) -> None:
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"dummy audio")

    fake_provider = FakeSTTProvider()
    result = await transcribe_file(str(audio_file), provider=fake_provider)

    assert result.provider == "fake"
    assert result.vendor_id == "fake-local"
    assert "Welcome to the EventAI demo" in result.text
    assert len(result.segments) >= 2
