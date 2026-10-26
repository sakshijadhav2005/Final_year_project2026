"""Claude (Anthropic API) as the text model for every pipeline step.

Set in .env:
    LLM_PROVIDER=anthropic
    ANTHROPIC_API_KEY=sk-ant-...
    ANTHROPIC_MODEL=claude-sonnet-5-5      # optional
    ANTHROPIC_EFFORT=low                   # optional: low | medium | high
"""

import json
import re
from typing import Any

import structlog

from app.core.config import get_settings
from app.providers.llm import LLMProvider

logger = structlog.get_logger("anthropic_llm")

# Current Claude models reject `temperature` and assistant prefill, so JSON is
# requested through the system prompt and parsed from the reply.
_JSON_RULE = (
    "\n\nOutput rules: reply with ONE valid JSON object and nothing else - "
    "no Markdown code fences, no text before or after the JSON."
)

# Process-wide memory, same idea as the Gemini provider: remember the model that
# works and never retry a model that returned "not found" / "permission denied".
_WORKING_MODEL: str | None = None
_DEAD_MODELS: set[str] = set()
_CLIENT = None
_CLIENT_KEY: str | None = None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {"result": value}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {"raw": text}
        return json.loads(match.group(0))


def _is_permanent(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    return status in {400, 401, 403, 404}


def get_client():
    """One shared async client (keeps HTTP connections warm between calls)."""
    global _CLIENT, _CLIENT_KEY
    settings = get_settings()
    if _CLIENT is None or _CLIENT_KEY != settings.anthropic_api_key:
        from anthropic import AsyncAnthropic

        _CLIENT = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,  # the SDK backs off on 429 / 5xx by itself
        )
        _CLIENT_KEY = settings.anthropic_api_key
    return _CLIENT


def candidate_models(fast: bool = False) -> list[str]:
    settings = get_settings()
    ordered = [_WORKING_MODEL, settings.anthropic_model, settings.anthropic_fallback_model]
    if fast:  # checking steps: the quick model first
        ordered = [settings.anthropic_fast_model, *ordered]
    return [m for m in dict.fromkeys(ordered) if m and m not in _DEAD_MODELS]


def effort_config() -> dict[str, Any]:
    effort = (get_settings().anthropic_effort or "").strip().lower()
    return {"effort": effort} if effort in {"low", "medium", "high", "xhigh", "max"} else {}


class AnthropicLLMProvider(LLMProvider):
    name = "anthropic"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3, fast: bool = False
    ) -> dict[str, Any]:
        global _WORKING_MODEL
        settings = get_settings()
        client = get_client()
        kwargs: dict[str, Any] = {}
        if effort_config():
            kwargs["output_config"] = effort_config()

        last_error: Exception | None = None
        tried = candidate_models(fast)
        for model in tried:
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=settings.anthropic_max_tokens,
                    system=system + _JSON_RULE,
                    messages=[{"role": "user", "content": user}],
                    **kwargs,
                )
                text = "".join(
                    block.text for block in response.content if getattr(block, "type", "") == "text"
                )
                if text.strip():
                    if not fast:
                        _WORKING_MODEL = model
                    return _extract_json(text)
            except Exception as exc:  # noqa: BLE001 - logged and handled by fallback
                last_error = exc
                if kwargs and getattr(exc, "status_code", None) == 400 and (
                    "effort" in str(exc).lower() or "output_config" in str(exc).lower()
                ):
                    # This model does not take the effort setting: drop it and try again.
                    kwargs = {}
                    try:
                        response = await client.messages.create(
                            model=model,
                            max_tokens=settings.anthropic_max_tokens,
                            system=system + _JSON_RULE,
                            messages=[{"role": "user", "content": user}],
                        )
                        text = "".join(
                            b.text for b in response.content if getattr(b, "type", "") == "text"
                        )
                        if text.strip():
                            if not fast:
                                _WORKING_MODEL = model
                            return _extract_json(text)
                    except Exception as retry_exc:  # noqa: BLE001
                        exc = last_error = retry_exc
                if _is_permanent(exc):
                    _DEAD_MODELS.add(model)
                    if _WORKING_MODEL == model:
                        _WORKING_MODEL = None
                logger.warning("claude_model_failed", model=model, error=str(exc)[:300])

        # Same safety net as Gemini: keep the demo working, but make it loud in the logs.
        logger.error(
            "claude_unavailable_using_fake_llm",
            tried=tried,
            error=str(last_error)[:300] if last_error else None,
        )
        from app.providers.fake_llm import FakeLLMProvider

        return await FakeLLMProvider().generate_json(system=system, user=user, temperature=temperature)
