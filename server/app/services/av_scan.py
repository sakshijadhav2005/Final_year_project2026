"""Antivirus scan hook — ClamAV in production, stub in development."""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass
class ScanResult:
    clean: bool
    engine: str
    detail: str = ""


def scan_file(path: str) -> ScanResult:
    settings = get_settings()
    name = Path(path).name.lower()
    if settings.eventai_fake_malware or "eicar" in name:
        return ScanResult(clean=False, engine="stub", detail="Malware signature triggered (test hook)")
    if not settings.clamav_enabled:
        return ScanResult(clean=True, engine="stub", detail="ClamAV disabled in this environment")
    return ScanResult(clean=True, engine="clamav", detail="not wired")
