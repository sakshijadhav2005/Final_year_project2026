from app.core.config import get_settings
from app.providers.fake_llm import FakeLLMProvider
from app.providers.fake_stt import FakeSTTProvider
from app.providers.llm import LLMProvider
from app.providers.stt import STTProvider


def get_stt_provider(provider_name: str | None = None) -> STTProvider:
    settings = get_settings()
    chosen = (provider_name or settings.stt_provider or "videodb").lower()

    if chosen == "fake":
        return FakeSTTProvider()

    if chosen == "videodb":
        from app.providers.videodb_stt import VideoDBSTTProvider

        if settings.videodb_api_key:
            return VideoDBSTTProvider(
                api_key=settings.videodb_api_key,
                collection=settings.videodb_collection,
                index_scenes=settings.videodb_index_scenes,
            )
        if not provider_name:
            # Fallback to FakeSTTProvider when no API key is provided in dev/test
            return FakeSTTProvider()
        return VideoDBSTTProvider()

    return FakeSTTProvider()


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.gemini_api_key:
        from app.providers.gemini_llm import GeminiLLMProvider

        return GeminiLLMProvider()
    return FakeLLMProvider()
