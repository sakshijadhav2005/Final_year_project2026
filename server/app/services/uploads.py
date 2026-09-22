from pathlib import Path

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm", ".txt", ".md"}
ALLOWED_MIME_PREFIXES = ("audio/", "video/", "text/")
BLOCKED_INNER = {".exe", ".js", ".bat", ".cmd", ".scr", ".com", ".msi", ".php"}


def validate_upload(filename: str, content_type: str | None, size_bytes: int) -> None:
    settings = get_settings()
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type {suffix or 'unknown'} is not allowed")
    parts = name.split(".")
    if len(parts) > 2:
        inner = {f".{part.lower()}" for part in parts[1:-1]}
        if inner & BLOCKED_INNER:
            raise ValueError("Double extension is not allowed")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")
    if content_type and not content_type.startswith(ALLOWED_MIME_PREFIXES) and suffix not in {".txt", ".md"}:
        raise ValueError("MIME type is not allowed")
