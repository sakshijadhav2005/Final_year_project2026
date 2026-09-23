import re
from pathlib import Path

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm", ".txt", ".md"}
ALLOWED_MIME_PREFIXES = ("audio/", "video/", "text/")
BLOCKED_INNER = {".exe", ".js", ".bat", ".cmd", ".scr", ".com", ".msi", ".php", ".sh", ".py"}


def sanitize_filename(filename: str) -> str:
    """Sanitizes user-provided filename preventing path traversal and unsafe characters."""
    if not filename:
        return "upload.bin"

    # Extract base name only, stripping any directory structure
    name = Path(filename).name
    # Strip null bytes and control chars
    name = name.replace("\x00", "").strip()

    # Prevent path traversal patterns
    name = re.sub(r"\.\.+", ".", name)
    name = name.replace("/", "").replace("\\", "")

    # Retain extension
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem

    # Sanitize stem: allow only alphanumeric, underscores, hyphens, and single dots
    safe_stem = re.sub(r"[^a-zA-Z0-9_\.-]", "_", stem)
    safe_stem = re.sub(r"_+", "_", safe_stem).strip("._-")

    if not safe_stem:
        safe_stem = "media_upload"

    safe_suffix = re.sub(r"[^a-zA-Z0-9\.]", "", suffix)
    return f"{safe_stem}{safe_suffix}" if safe_suffix else safe_stem


def validate_upload_metadata(filename: str, content_type: str | None) -> str:
    """Validates filename extension, double extensions, and MIME type before reading content."""
    clean_name = sanitize_filename(filename)
    suffix = Path(clean_name).suffix.lower()

    if not suffix or suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{suffix or 'unknown'}' is not allowed")

    parts = clean_name.split(".")
    if len(parts) > 2:
        inner = {f".{part.lower()}" for part in parts[1:-1]}
        if inner & BLOCKED_INNER:
            raise ValueError("Double extension with executable/script type is not allowed")

    if (
        content_type
        and not content_type.startswith(ALLOWED_MIME_PREFIXES)
        and suffix not in {".txt", ".md"}
    ):
        raise ValueError(f"MIME type '{content_type}' is not allowed")

    return clean_name


def validate_upload(filename: str, content_type: str | None, size_bytes: int) -> None:
    """Backwards-compatible complete upload validator."""
    if size_bytes <= 0:
        raise ValueError("Empty file upload is not allowed")

    validate_upload_metadata(filename, content_type)
    settings = get_settings()
    max_bytes = settings.max_upload_bytes
    if size_bytes > max_bytes:
        raise ValueError(f"File exceeds {settings.effective_max_upload_mb} MB limit")

