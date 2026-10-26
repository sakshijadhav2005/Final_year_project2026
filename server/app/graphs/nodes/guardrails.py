from typing import Any

from app.graphs.state import JobGraphState
from app.services.guardrails import verify_batch_with_llm


async def guardrail(state: JobGraphState) -> dict[str, Any]:
    """Checks every draft for grounding + moderation in ONE batched LLM call.

    If some drafts fail, only those content types are sent back for regeneration
    (once); passing drafts are kept as they are.
    """
    transcript = state.get("transcript_text") or ""
    generated = [dict(p) for p in (state.get("generated") or [])]
    if not generated:
        return {"route": "needs_review", "guardrail": {"pass": False, "issues": ["No content generated"]}}

    verdicts = await verify_batch_with_llm(generated, transcript)

    issues: list[str] = []
    failed_types: list[str] = []
    for piece in generated:
        ctype = str(piece.get("type"))
        v = verdicts.get(ctype) or {}
        piece["moderation"] = v.get("moderation", {"pass": True, "hits": []})
        piece["grounding"] = v.get("grounding", {"pass": True, "issues": []})
        if not piece["moderation"].get("pass", True):
            issues.append(f"moderation:{ctype}")
        if not piece["grounding"].get("pass", True):
            issues.append(f"grounding:{ctype}")
        if issues and issues[-1].endswith(f":{ctype}") and ctype not in failed_types:
            failed_types.append(ctype)

    retry_count = int(state.get("retry_count") or 0)
    if failed_types and retry_count < 1:
        return {
            "route": "retry_generate",
            "retry_count": retry_count + 1,
            "retry_types": failed_types,
            "guardrail": {"pass": False, "issues": issues},
            "generated": generated,
        }
    if issues:
        return {
            "route": "needs_review",
            "guardrail": {"pass": False, "issues": issues},
            "generated": generated,
        }
    return {"route": "continue", "guardrail": {"pass": True, "issues": []}, "generated": generated}


async def persist_fail(state: JobGraphState) -> dict[str, Any]:
    return {"route": "needs_review"}
