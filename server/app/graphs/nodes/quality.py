from typing import Any

from app.graphs.state import JobGraphState


async def quality_check(state: JobGraphState) -> dict[str, Any]:
    """Pre-flight quality gate validating audio duration and silence ratio."""
    quality = state.get("quality") or {}
    if (
        quality.get("ok") is False
        or quality.get("recommendation") == "needs_reupload"
        or quality.get("status") == "needs_reupload"
    ):
        return {"route": "needs_reupload"}
    avg = state.get("avg_confidence")
    if isinstance(avg, int | float) and avg < 0.35:
        return {"route": "needs_reupload"}
    return {"route": "continue"}
