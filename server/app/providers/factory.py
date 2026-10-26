from app.core.config import get_settings
from app.providers.fake_llm import FakeLLMProvider
from app.providers.fake_stt import FakeSTTProvider
from app.providers.llm import LLMProvider
from app.providers.stt import STTProvider


def get_stt_provider() -> STTProvider:
    """Pick the speech-to-text engine from STT_PROVIDER.

    auto (default): Gemini when a Gemini key exists (fast, one upload), otherwise
    VideoDB, otherwise the offline fake. "videodb" / "gemini" force one engine.
    """
    settings = get_settings()
    choice = (settings.stt_provider or "auto").strip().lower()

    def _gemini() -> STTProvider:
        from app.providers.gemini_stt import GeminiSTTProvider

        return GeminiSTTProvider()

    def _videodb() -> STTProvider:
        from app.providers.videodb_stt import VideoDBSTTProvider

        return VideoDBSTTProvider()

    if choice == "videodb" and settings.videodb_api_key:
        return _videodb()
    if choice in {"gemini", "auto"} and settings.gemini_api_key:
        return _gemini()
    if settings.videodb_api_key:
        return _videodb()
    if settings.gemini_api_key:
        return _gemini()
    return FakeSTTProvider()


def get_llm_provider() -> LLMProvider:
    """Use the provider named in LLM_PROVIDER. Having a Portkey key in .env no longer
    silently reroutes every call through the Portkey -> OpenAI -> Groq -> Gemini chain."""
    settings = get_settings()
    provider = (settings.llm_provider or "gemini").strip().lower()
    if provider == "fake":
        return FakeLLMProvider()
    if provider == "vertex" and settings.google_cloud_project:
        from app.providers.vertex_llm import VertexLLMProvider

        return VertexLLMProvider()
    if provider in {"anthropic", "claude"} and settings.anthropic_api_key:
        from app.providers.anthropic_llm import AnthropicLLMProvider

        return AnthropicLLMProvider()
    if provider == "portkey" and (settings.portkey_api_key or settings.openai_api_key):
        from app.providers.portkey_llm import PortkeyLLMProvider

        return PortkeyLLMProvider()
    if settings.gemini_api_key:
        from app.providers.gemini_llm import GeminiLLMProvider

        return GeminiLLMProvider()
    if settings.portkey_api_key or settings.openai_api_key:
        from app.providers.portkey_llm import PortkeyLLMProvider

        return PortkeyLLMProvider()
    if settings.anthropic_api_key:
        from app.providers.anthropic_llm import AnthropicLLMProvider

        return AnthropicLLMProvider()
    return FakeLLMProvider()
