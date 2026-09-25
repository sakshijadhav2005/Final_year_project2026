from app.core.config import get_settings
from app.providers.fake_llm import FakeLLMProvider
from app.providers.fake_stt import FakeSTTProvider
from app.providers.llm import LLMProvider
from app.providers.stt import STTProvider


def get_stt_provider() -> STTProvider:
    settings = get_settings()
    if settings.videodb_api_key:
        from app.providers.videodb_stt import VideoDBSTTProvider

        return VideoDBSTTProvider()
    return FakeSTTProvider()


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "portkey" or settings.portkey_api_key:
        from app.providers.portkey_llm import PortkeyLLMProvider
        return PortkeyLLMProvider()
    if settings.gemini_api_key:
        from app.providers.gemini_llm import GeminiLLMProvider
        return GeminiLLMProvider()
    return FakeLLMProvider()
