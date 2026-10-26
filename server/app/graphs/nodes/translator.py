import asyncio
import json
from typing import Any

from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.services.resilience import llm_circuit, with_backoff

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

SYSTEM = (
    "You are a professional translator for event marketing copy. Translate every draft "
    "faithfully, keep Markdown structure, emojis, @handles and #hashtags unchanged. "
    "Reply with JSON only."
)


async def _translate_language(llm, pieces: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    """Translate ALL drafts into one language with a single LLM call."""
    name = LANG_MAP.get(code, code)
    drafts = {str(p.get("type")): {"title": p.get("title") or "", "body": p.get("body") or ""} for p in pieces}
    user = (
        "TASK=translation_batch\n"
        f"Translate each draft into {name}. Return JSON exactly as "
        '{"drafts": {"<draft_type>": {"title": "...", "body": "..."}}} using the same keys.\n'
        f"<DRAFTS_JSON>\n{json.dumps(drafts, ensure_ascii=False)}\n</DRAFTS_JSON>"
    )
    try:
        result = await with_backoff(
            lambda: llm.generate_json(system=SYSTEM, user=user, temperature=0.2, fast=True),
            circuit=llm_circuit,
            attempts=2,
        )
        translated = result.get("drafts") if isinstance(result.get("drafts"), dict) else {}
    except Exception:
        translated = {}
    if not translated:
        from app.services import degraded

        degraded.mark(f"translation_missing:{code}")  # the English text is kept instead

    out = []
    for p in pieces:
        ctype = str(p.get("type"))
        t = translated.get(ctype) if isinstance(translated.get(ctype), dict) else {}
        out.append(
            {
                "type": ctype,
                "language": code,
                "title": t.get("title") or p.get("title"),
                "body": t.get("body") or t.get("text") or p.get("body"),
                "parent_type": ctype,
            }
        )
    return out


async def translation(state: JobGraphState) -> dict[str, Any]:
    """One call per target language (all drafts batched), languages run in parallel."""
    languages = [lang for lang in (state.get("target_languages") or ["en"]) if lang and lang != "en"]
    pieces = state.get("generated") or []
    if not languages or not pieces:
        return {"translations": []}
    llm = get_llm_provider()
    per_lang = await asyncio.gather(*(_translate_language(llm, pieces, code) for code in languages))
    return {"translations": [item for batch in per_lang for item in batch]}
