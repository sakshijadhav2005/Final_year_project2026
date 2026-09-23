from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    confidence: float | None = None
    speaker: str | None = None


@dataclass
class TranscriptResult:
    text: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    avg_confidence: float | None = None
    provider: str = "unknown"
    vendor_id: str | None = None
    scenes: list[dict[str, Any]] = field(default_factory=list)


class STTProvider(ABC):
    """Swap VideoDB for Whisper/AssemblyAI without changing the graph."""

    name: str

    @abstractmethod
    async def transcribe(self, file_path: str) -> TranscriptResult:
        raise NotImplementedError
