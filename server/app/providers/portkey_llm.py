import json
import re
from typing import Any

from app.core.config import get_settings
from app.providers.llm import LLMProvider
from app.services.gemini import wrap_transcript
from app.providers.fake_llm import FakeLLMProvider
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


class PortkeyLLMProvider(LLMProvider):
    name = "portkey"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3
    ) -> dict[str, Any]:
        settings = get_settings()
        
        # RATE LIMIT BYPASS: Ensure we can bypass limits for everything now if we want!
        # The user requested to use OpenAI model through Portkey to overcome rate limits.
        task = "unknown"
        for line in user.splitlines():
            if line.startswith("TASK="):
                task = line.split("=", 1)[1].strip()
                break
                
        # If API keys are missing, fallback to FakeLLM to prevent crash
        if not settings.portkey_api_key and not settings.openai_api_key:
             return await FakeLLMProvider().generate_json(
                system=system, user=user, temperature=temperature
             )

        try:
            from openai import AsyncOpenAI
            
            async def call_openai():
                if not settings.openai_api_key:
                    raise ValueError("No OpenAI key")
                client = AsyncOpenAI(
                    api_key=settings.openai_api_key,
                )
                res = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                return _extract_json(res.choices[0].message.content)

            async def call_groq():
                if not settings.groq_api_key:
                    raise ValueError("No Groq key")
                client = AsyncOpenAI(
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
                res = await client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                return _extract_json(res.choices[0].message.content)
                
            async def call_gemini():
                if not settings.gemini_api_key:
                    raise ValueError("No Gemini key")
                from app.providers.gemini_llm import GeminiLLMProvider
                return await GeminiLLMProvider().generate_json(system=system, user=user, temperature=temperature)

            # Execution chain: OpenAI -> Groq -> Gemini
            strategies = [call_openai, call_groq, call_gemini]
            for attempt, strategy in enumerate(strategies):
                try:
                    return await with_backoff(strategy, circuit=llm_circuit, attempts=2)
                except Exception as exc:
                    print(f"[PortkeyLLMProvider] Strategy {attempt} failed: {exc}")
                    continue
                
        except Exception as exc:
            print(f"[PortkeyLLMProvider] Fatal error in fallback chain: {exc}")
            
        # Fallback if anything fails
        return await FakeLLMProvider().generate_json(
            system=system, user=user, temperature=temperature
        )

