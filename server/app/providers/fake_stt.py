from pathlib import Path

from app.providers.stt import STTProvider, TranscriptResult, TranscriptSegment


class FakeSTTProvider(STTProvider):
    """Fixture transcript so the UI and graph work without VideoDB keys."""

    name = "fake"

    async def transcribe(self, file_path: str) -> TranscriptResult:
        Path(file_path).name
        return TranscriptResult(
            text=(
                "Welcome to the EventAI demo session. Today we discuss how recordings "
                "become publish-ready summaries, blogs, and social posts."
            ),
            language="en",
            avg_confidence=0.92,
            provider=self.name,
            vendor_id="fake-local",
            segments=[
                TranscriptSegment(
                    text="Welcome to the EventAI demo session.",
                    start=0.0,
                    end=4.2,
                    confidence=0.95,
                    speaker="host",
                ),
                TranscriptSegment(
                    text="Today we discuss how recordings become publish-ready content.",
                    start=4.2,
                    end=10.0,
                    confidence=0.89,
                    speaker="host",
                ),
            ],
        )
