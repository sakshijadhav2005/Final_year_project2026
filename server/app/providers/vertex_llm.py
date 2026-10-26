import asyncio
from typing import Any

import structlog

from app.core.config import get_settings
from app.providers.gemini_llm import _extract_json, _is_permanent, candidate_models
from app.providers.llm import LLMProvider

logger = structlog.get_logger("vertex_llm")

# Process-wide memory, same idea as the Gemini provider.
_CLIENTS: dict[tuple[str, str], object] = {}
_DEAD_MODELS: set[str] = set()


def _client(location: str | None = None):
    """Gemini on Vertex AI. Auth comes from Application Default Credentials
    (`gcloud auth application-default login` locally, the service account in the cloud).
    `location` overrides GOOGLE_CLOUD_LOCATION (embeddings use a regional endpoint)."""
    from google import genai

    settings = get_settings()
    key = (settings.google_cloud_project, location or settings.google_cloud_location)
    if key not in _CLIENTS:
        _CLIENTS[key] = genai.Client(vertexai=True, project=key[0], location=key[1])
    return _CLIENTS[key]


class VertexLLMProvider(LLMProvider):
    name = "vertex"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3, fast: bool = False
    ) -> dict[str, Any]:
        settings = get_settings()
        from google.genai import types

        from app.providers.fake_llm import FakeLLMProvider
        from app.services import degraded
        from app.services.resilience import model_circuit, with_backoff

        client = _client()
        # The configured model always goes first; one that keeps failing is moved to the
        # back while its circuit is open and tried first again once the window has passed.
        ordered = [
            settings.vertex_model or settings.gemini_model_generate,
            "gemini-3.6-flash",
            "gemini-3.1-flash-lite",
        ]
        if fast:
            ordered = [settings.vertex_fast_model or settings.gemini_model_fast, *ordered]
        models = candidate_models(ordered, _DEAD_MODELS)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
        )

        last_error: Exception | None = None
        for model_name in models:
            circuit = model_circuit(model_name)

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
                    response = await with_backoff(_call, circuit=circuit, attempts=2)
                if response and response.text:
                    circuit.success()
                    return _extract_json(response.text)
                circuit.failure()  # an empty answer counts as a failed call
            except Exception as exc:
                last_error = exc
                if _is_permanent(exc):
                    _DEAD_MODELS.add(model_name)
                logger.warning("vertex_model_failed", model=model_name, error=str(exc)[:300])
                continue

        logger.error(
            "vertex_unavailable_using_fake_llm",
            tried=models,
            error=str(last_error)[:300] if last_error else None,
        )
        degraded.mark("llm_offline_template")
        return await FakeLLMProvider().generate_json(
            system=system, user=user, temperature=temperature
        )
