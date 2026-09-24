from typing import Any

from app.graphs.state import JobGraphState
from app.services.guardrails import verify_content_with_llm


async def guardrail(state: JobGraphState) -> dict[str, Any]:
    transcript = state.get("transcript_text") or ""
    issues: list[str] = []
    generated = state.get("generated") or []
    
    if not generated:
        issues.append("No content generated")
        
    for piece in generated:
        body = str(piece.get("body") or "")
        
        # We now use the single LLM-as-a-judge call to get both moderation and grounding!
        result = await verify_content_with_llm(body, transcript)
        
        mod = result["moderation"]
        ground = result["grounding"]
        
        piece["moderation"] = mod
        piece["grounding"] = ground
        
        if not mod.get("pass", True):
            issues.append(f"moderation:{piece.get('type')}")
        if not ground.get("pass", True):
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
