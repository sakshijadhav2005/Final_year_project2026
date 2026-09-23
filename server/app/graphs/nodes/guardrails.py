from typing import Any

from app.graphs.state import JobGraphState
from app.services.guardrails import grounding_check, moderate_text


async def guardrail(state: JobGraphState) -> dict[str, Any]:
    transcript = state.get("transcript_text") or ""
    issues: list[str] = []
    generated = state.get("generated") or []
    if not generated:
        issues.append("No content generated")
    for piece in generated:
        body = str(piece.get("body") or "")
        mod = moderate_text(body)
        ground = grounding_check(body, transcript)
        piece["moderation"] = mod
        piece["grounding"] = ground
        if not mod["pass"]:
            issues.append(f"moderation:{piece.get('type')}")
        if not ground["pass"]:
            issues.append(f"grounding:{piece.get('type')}")
    retry_count = int(state.get("retry_count") or 0)
    if issues and retry_count < 1:
        return {
            "route": "retry_generate",
            "retry_count": retry_count + 1,
            "guardrail": {"pass": False, "issues": issues},
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
