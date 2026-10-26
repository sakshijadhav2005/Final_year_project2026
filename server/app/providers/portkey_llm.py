from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm import LLMProvider
from app.services.resilience import llm_circuit, with_backoff


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {"raw": text}
        return json.loads(match.group(0))


# Remember which route works so later calls skip the ones that fail.
_WORKING_STRATEGY: str | None = None
_DEAD_STRATEGIES: set[str] = set()


def _is_permanent(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    if any(t in text for t in ("429", "rate", "timeout", "timed out", "overloaded", "503", "502")):
        return False
    return any(
        t in text
        for t in ("no ", "401", "403", "404", "400", "invalid", "not found", "unauthorized", "permission", "api key", "quota")
    )


class PortkeyLLMProvider(LLMProvider):
    """Multi-provider AI Gateway with Portkey, OpenAI, Groq, and Gemini fallback routing."""

    name = "portkey"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3, fast: bool = False
    ) -> dict[str, Any]:
        settings = get_settings()

        from openai import AsyncOpenAI

        async def call_portkey() -> dict[str, Any]:
            if not settings.portkey_api_key:
                raise ValueError("No Portkey API key")
            headers = {
                "x-portkey-api-key": settings.portkey_api_key,
            }
            client = AsyncOpenAI(
                api_key=settings.openai_api_key or settings.portkey_api_key,
                base_url="https://api.portkey.ai/v1",
                default_headers=headers,
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = res.choices[0].message.content or "{}"
            return _extract_json(content)

        async def call_openai() -> dict[str, Any]:
            if not settings.openai_api_key:
                raise ValueError("No OpenAI API key")
            client = AsyncOpenAI(
                api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds, max_retries=0
            )
            res = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = res.choices[0].message.content or "{}"
            return _extract_json(content)

        async def call_groq() -> dict[str, Any]:
            if not settings.groq_api_key:
                raise ValueError("No Groq API key")
            client = AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )
            res = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = res.choices[0].message.content or "{}"
            return _extract_json(content)

        async def call_gemini() -> dict[str, Any]:
            if not settings.gemini_api_key:
                raise ValueError("No Gemini API key")
            from app.providers.gemini_llm import GeminiLLMProvider

            return await GeminiLLMProvider().generate_json(
                system=system, user=user, temperature=temperature
            )

        # Gateway priority order: Portkey -> OpenAI -> Groq -> Gemini, but the route that
        # worked last time goes first and routes with permanent errors are skipped.
        global _WORKING_STRATEGY
        strategies = {
            "portkey": call_portkey,
            "openai": call_openai,
            "groq": call_groq,
            "gemini": call_gemini,
        }
        order = [_WORKING_STRATEGY, "portkey", "openai", "groq", "gemini"]
        for name in [n for n in dict.fromkeys(order) if n and n not in _DEAD_STRATEGIES]:
            strategy = strategies[name]
            try:
                try:
                    result = await strategy()
                except Exception as first:
                    if _is_permanent(first):
                        raise
                    result = await with_backoff(strategy, circuit=llm_circuit, attempts=2)
                _WORKING_STRATEGY = name
                return result
            except Exception as exc:
                if _is_permanent(exc):
                    _DEAD_STRATEGIES.add(name)
                continue

        # Fallback if all providers are unavailable or unset
        return await FakeLLMProvider().generate_json(
            system=system, user=user, temperature=temperature
        )
