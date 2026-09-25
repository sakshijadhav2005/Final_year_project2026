import asyncio
from typing import Any

from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.providers.gemini_llm import build_user_prompt, generation_system
from app.services.resilience import llm_circuit, with_backoff


async def translation(state: JobGraphState) -> dict[str, Any]:
    languages = [
        lang for lang in (state.get("target_languages") or ["en"]) if lang and lang != "en"
    ]
    if not languages:
        return {"translations": []}
    llm = get_llm_provider()
    LANG_MAP = {
        "hi": "Hindi",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "ja": "Japanese",
        "pt": "Portuguese",
        "it": "Italian",
        "zh": "Chinese",
        "ar": "Arabic",
        "ru": "Russian",
        "ko": "Korean",
    }
    
    generated_pieces = state.get("generated") or []
    if not generated_pieces:
        return {"translations": []}

    tasks = []
    
    for lang in languages:
        full_lang_name = LANG_MAP.get(lang, lang)
        for piece in generated_pieces:
            async def _translate_task(p=piece, l_code=lang, l_name=full_lang_name):
                async def _call() -> dict[str, Any]:
                    return await llm.generate_json(
                        system=generation_system(),
                        user=build_user_prompt(
                            "translation",
                            state.get("transcript_text", "")[:4000],
                            f"Translate this {p.get('type')} into {l_name}. Return JSON with keys 'title', 'body'.\n"
                            f"Title={p.get('title')}\nBody={p.get('body')}",
                        ),
                        temperature=0.2,
                    )

                result = await with_backoff(_call, circuit=llm_circuit)
                return {
                    "type": p.get("type"),
                    "language": l_code,
                    "title": result.get("title") or p.get("title"),
                    "body": result.get("text") or result.get("body") or p.get("body"),
                    "parent_type": p.get("type"),
                }

            tasks.append(_translate_task())

    translations = await asyncio.gather(*tasks)
    return {"translations": list(translations)}
