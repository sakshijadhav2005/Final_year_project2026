from typing import Any, Literal, TypedDict


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
    generated: list[dict[str, Any]]
    guardrail: dict[str, Any]
    translations: list[dict[str, Any]]
    use_org_memory: bool
    user_memory: dict[str, Any]
    route: Literal["continue", "retry_generate", "needs_review", "needs_reupload", "failed"]
    retry_count: int
