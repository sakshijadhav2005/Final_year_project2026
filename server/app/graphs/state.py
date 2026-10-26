from typing import Annotated, Any, Literal, TypedDict


def merge_generated(
    left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Reducer for generated pieces.

    Parallel generator branches each add one piece; the guardrail node writes the
    annotated pieces back, and a guardrail retry regenerates them. Keeping only the
    newest piece per content type prevents duplicates in every one of those paths.
    """
    merged: dict[str, dict[str, Any]] = {}
    for piece in [*(left or []), *(right or [])]:
        merged[str(piece.get("type"))] = piece
    return list(merged.values())


class JobGraphState(TypedDict, total=False):
    job_id: str
    user_id: str
    transcript_text: str
    transcript_segments: list[dict[str, Any]]
    avg_confidence: float | None
    quality: dict[str, Any]
    topics: dict[str, Any] | None
    highlights: dict[str, Any] | None
    speakers: dict[str, Any] | None
    sentiment: dict[str, Any] | None
    brief: dict[str, Any] | None
    rag_chunks: list[dict[str, Any]]
    requested_types: list[str]
    target_languages: list[str]
    generated: Annotated[list[dict[str, Any]], merge_generated]
    guardrail: dict[str, Any]
    translations: list[dict[str, Any]]
    use_org_memory: bool
    user_memory: dict[str, Any]
    route: Literal["continue", "retry_generate", "needs_review", "needs_reupload", "failed"]
    retry_count: int
    retry_types: list[str]
