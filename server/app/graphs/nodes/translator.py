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
    translations: list[dict[str, Any]] = []
    for lang in languages:
        for piece in state.get("generated") or []:

            async def _call(p=piece, language=lang) -> dict[str, Any]:
                return await llm.generate_json(
                    system=generation_system(),
                    user=build_user_prompt(
                        "translation",
                        state.get("transcript_text", ""),
                        f"Translate this {p.get('type')} into {language}. JSON with keys title, body.\n"
                        f"Title={p.get('title')}\nBody={p.get('body')}",
                    ),
                    temperature=0.2,
                )

            result = await with_backoff(_call, circuit=llm_circuit)
            translations.append(
                {
                    "type": piece.get("type"),
                    "language": lang,
                    "title": result.get("title") or piece.get("title"),
                    "body": result.get("text") or result.get("body") or piece.get("body"),
                    "parent_type": piece.get("type"),
                }
            )
    return {"translations": translations}
