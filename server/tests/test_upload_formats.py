import pytest
from app.providers.gemini_stt import _mime_for
from app.services.uploads import validate_upload


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("talk.ogg", "audio/ogg"),
        ("talk.ogg", "application/ogg"),
        ("talk.ogg", "video/ogg"),
        ("voice.opus", "audio/opus"),
        ("talk.flac", "audio/x-flac"),
        ("talk.aac", "audio/aac"),
        ("talk.mkv", "video/x-matroska"),
        ("talk.avi", "video/x-msvideo"),
        ("talk.mp3", "application/octet-stream"),
    ],
)
def test_common_media_formats_are_accepted(name, mime):
    validate_upload(name, mime, 1024)


@pytest.mark.parametrize(
    ("name", "mime"),
    [("evil.exe", "application/octet-stream"), ("talk.ogg", "application/pdf"), ("a.exe.ogg", "audio/ogg")],
)
def test_unsafe_uploads_are_still_rejected(name, mime):
    with pytest.raises(ValueError):
        validate_upload(name, mime, 1024)


def test_gemini_gets_an_explicit_mime_type():
    assert _mime_for("/x/talk.ogg") == "audio/ogg"
    assert _mime_for("/x/talk.OPUS") == "audio/ogg"
    assert _mime_for("/x/talk.mkv") == "video/x-matroska"
