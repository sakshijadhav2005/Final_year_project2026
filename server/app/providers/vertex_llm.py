import asyncio
from typing import Any

import structlog

from app.core.config import get_settings
from app.providers.gemini_llm import _extract_json, _is_permanent
from app.providers.llm import LLMProvider

logger = structlog.get_logger("vertex_llm")

# Process-wide memory, same idea as the Gemini provider.
_CLIENT = None
_CLIENT_KEY: tuple[str, str] | None = None
_WORKING_MODEL: str | None = None
_WORKING_FAST_MODEL: str | None = None
_DEAD_MODELS: set[str] = set()


def _client():
    """Gemini on Vertex AI. Auth comes from Application Default Credentials
    (`gcloud auth application-default login` locally, the service account in the cloud)."""
    global _CLIENT, _CLIENT_KEY
    from google import genai

    settings = get_settings()
    key = (settings.google_cloud_project, settings.google_cloud_location)
    if _CLIENT is None or _CLIENT_KEY != key:
        _CLIENT = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        _CLIENT_KEY = key
    return _CLIENT


class VertexLLMProvider(LLMProvider):
    name = "vertex"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3, fast: bool = False
    ) -> dict[str, Any]:
        global _WORKING_MODEL, _WORKING_FAST_MODEL
        settings = get_settings()
        from google.genai import types

        from app.providers.fake_llm import FakeLLMProvider
        from app.services.resilience import llm_circuit, with_backoff

        client = _client()
        ordered = [
            _WORKING_MODEL,
            settings.vertex_model or settings.gemini_model_generate,
            "gemini-3.6-flash",
            "gemini-3.1-flash-lite",
        ]
        if fast:
            ordered = [
                _WORKING_FAST_MODEL,
                settings.vertex_fast_model or settings.gemini_model_fast,
                *ordered,
            ]
        candidate_models = [m for m in dict.fromkeys(ordered) if m and m not in _DEAD_MODELS]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
        )

        last_error: Exception | None = None
        for model_name in candidate_models:

            async def _call(model_name=model_name):
                return await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name, contents=user, config=config
                    ),
                    timeout=settings.llm_timeout_seconds,
                )

            try:
                try:
                    response = await _call()
                except Exception as first:
                    if _is_permanent(first):
                        raise
                    response = await with_backoff(_call, circuit=llm_circuit, attempts=2)
                if response and response.text:
                    if fast:
                        _WORKING_FAST_MODEL = model_name
                    else:
                        _WORKING_MODEL = model_name
                    return _extract_json(response.text)
            except Exception as exc:
                last_error = exc
                if _is_permanent(exc):
                    _DEAD_MODELS.add(model_name)
                    if _WORKING_MODEL == model_name:
                        _WORKING_MODEL = None
                    if _WORKING_FAST_MODEL == model_name:
                        _WORKING_FAST_MODEL = None
                logger.warning("vertex_model_failed", model=model_name, error=str(exc)[:300])
                continue

        logger.error(
            "vertex_unavailable_using_fake_llm",
            tried=candidate_models,
            error=str(last_error)[:300] if last_error else None,
        )
        return await FakeLLMProvider().generate_json(
            system=system, user=user, temperature=temperature
        )
