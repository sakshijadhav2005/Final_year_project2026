import asyncio
import json
from typing import Any

from app.core.config import get_settings
from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.services.provenance import content_tokens
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


BACK_SYSTEM = (
    "You translate event marketing copy into English for a quality check. Translate "
    "literally and faithfully; do not improve, shorten or restore anything. Keep Markdown, "
    "emojis, @handles and #hashtags unchanged. Reply with JSON only."
)


def back_translation_score(original: str, back: str) -> float:
    """F1 overlap of content words (stemmed, stop words removed) between the English
    original and its back-translation. 1.0 = same content words, 0.0 = nothing shared."""
    a, b = content_tokens(original), content_tokens(back)
    if not a or not b:
        return 0.0
    counts: dict[str, int] = {}
    for tok in a:
        counts[tok] = counts.get(tok, 0) + 1
    common = 0
    for tok in b:
        if counts.get(tok, 0) > 0:
            counts[tok] -= 1
            common += 1
    if not common:
        return 0.0
    precision, recall = common / len(b), common / len(a)
    return round(2 * precision * recall / (precision + recall), 3)


async def _back_translate(llm, translated: dict[str, dict], code: str) -> dict[str, dict]:
    """Translate one language's drafts back into English with a single call."""
    name = LANG_MAP.get(code, code)
    user = (
        "TASK=back_translation_batch\n"
        f"Translate each {name} draft back into English. Return JSON exactly as "
        '{"drafts": {"<draft_type>": {"title": "...", "body": "..."}}} using the same keys.\n'
        f"<DRAFTS_JSON>\n{json.dumps(translated, ensure_ascii=False)}\n</DRAFTS_JSON>"
    )
    try:
        result = await with_backoff(
            lambda: llm.generate_json(system=BACK_SYSTEM, user=user, temperature=0.0, fast=True),
            circuit=llm_circuit,
            attempts=2,
        )
    except Exception:
        return {}
    drafts = result.get("drafts")
    return drafts if isinstance(drafts, dict) else {}


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

    settings = get_settings()
    backs: dict[str, dict] = {}
    if translated and settings.back_translation_enabled:
        backs = await _back_translate(
            llm, {k: v for k, v in translated.items() if isinstance(v, dict)}, code
        )

    out = []
    for p in pieces:
        ctype = str(p.get("type"))
        t = translated.get(ctype) if isinstance(translated.get(ctype), dict) else {}
        item = {
            "type": ctype,
            "language": code,
            "title": t.get("title") or p.get("title"),
            "body": t.get("body") or t.get("text") or p.get("body"),
            "parent_type": ctype,
        }
        if settings.back_translation_enabled:
            item["back_translation"] = _check(p, t, backs.get(ctype), settings)
        out.append(item)
    return out


def _check(original: dict, translated: dict, back, settings) -> dict[str, Any]:
    """Back-translation verdict for one draft, shown to the reviewer."""
    if not translated:
        return {"status": "untranslated", "pass": False, "score": None}
    if not isinstance(back, dict) or not (back.get("body") or back.get("text")):
        return {"status": "unchecked", "pass": None, "score": None}
    back_text = f"{back.get('title') or ''}\n{back.get('body') or back.get('text') or ''}"
    original_text = f"{original.get('title') or ''}\n{original.get('body') or ''}"
    score = back_translation_score(original_text, back_text)
    passed = score >= settings.back_translation_min_score
    return {
        "status": "pass" if passed else "low_agreement",
        "pass": passed,
        "score": score,
        "min_score": settings.back_translation_min_score,
        "back_text": back_text.strip()[:4000],
    }


async def translation(state: JobGraphState) -> dict[str, Any]:
    """One call per target language (all drafts batched), languages run in parallel."""
    languages = [lang for lang in (state.get("target_languages") or ["en"]) if lang and lang != "en"]
    pieces = state.get("generated") or []
    if not languages or not pieces:
        return {"translations": []}
    llm = get_llm_provider()
    per_lang = await asyncio.gather(*(_translate_language(llm, pieces, code) for code in languages))
    return {"translations": [item for batch in per_lang for item in batch]}
