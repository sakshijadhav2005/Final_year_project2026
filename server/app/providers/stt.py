from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    confidence: float | None = None
    speaker: str | None = None
    # [start, end] seconds (recording time) where someone is speaking inside this segment.
    # Lets provenance place words on speech time instead of spreading them evenly.
    speech: list[list[float]] | None = None


@dataclass
class TranscriptResult:
    text: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    avg_confidence: float | None = None
    provider: str = "unknown"
    vendor_id: str | None = None


class STTProvider(ABC):
    """Swap VideoDB for Whisper/AssemblyAI without changing the graph."""

    name: str

    @abstractmethod
    async def transcribe(self, file_path: str) -> TranscriptResult:
        raise NotImplementedError
