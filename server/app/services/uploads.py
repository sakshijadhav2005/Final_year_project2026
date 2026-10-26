from pathlib import Path

from app.core.config import get_settings

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".oga", ".opus", ".flac", ".aac", ".weba"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".3gp"}
TEXT_EXTENSIONS = {".txt", ".md"}
ALLOWED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | TEXT_EXTENSIONS
ALLOWED_MIME_PREFIXES = ("audio/", "video/", "text/")
# Browsers label some media generically (Windows often sends application/ogg or
# application/octet-stream). The extension whitelist above is the real check.
GENERIC_MEDIA_MIMES = {"application/ogg", "application/octet-stream", "application/x-matroska"}
BLOCKED_INNER = {".exe", ".js", ".bat", ".cmd", ".scr", ".com", ".msi", ".php"}


def validate_upload(filename: str, content_type: str | None, size_bytes: int) -> None:
    settings = get_settings()
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type {suffix or 'unknown'} is not allowed. Use audio "
            f"({', '.join(sorted(AUDIO_EXTENSIONS))}), video ({', '.join(sorted(VIDEO_EXTENSIONS))}) "
            "or a .txt/.md transcript"
        )
    parts = name.split(".")
    if len(parts) > 2:
        inner = {f".{part.lower()}" for part in parts[1:-1]}
        if inner & BLOCKED_INNER:
            raise ValueError("Double extension is not allowed")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")
    if (
        content_type
        and not content_type.startswith(ALLOWED_MIME_PREFIXES)
        and content_type not in GENERIC_MEDIA_MIMES
        and suffix not in TEXT_EXTENSIONS
    ):
        raise ValueError("MIME type is not allowed")
