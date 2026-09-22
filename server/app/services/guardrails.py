import re

BLOCKLIST = ("kill all", "hate speech-demo-token")


def confidence_badge(score: float | None) -> str:
    if score is None:
        return "medium"
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def moderate_text(text: str) -> dict:
    lowered = text.lower()
    hits = [term for term in BLOCKLIST if term in lowered]
    return {"pass": not hits, "hits": hits}


def grounding_check(body: str, transcript: str) -> dict:
    transcript_tokens = {t.lower() for t in re.findall(r"[a-zA-Z]{4,}", transcript)}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    unsupported: list[str] = []
    supported = 0
    for sentence in sentences:
        words = [t.lower() for t in re.findall(r"[a-zA-Z]{4,}", sentence)]
        if not words:
            continue
        overlap = sum(1 for w in words if w in transcript_tokens) / max(len(set(words)), 1)
        if overlap < 0.12 and len(words) > 8:
            unsupported.append(sentence)
        else:
            supported += 1
    return {
        "pass": len(unsupported) <= max(1, len(sentences) // 4),
        "supported_sentences": supported,
        "unsupported": unsupported[:8],
    }


def should_use_rag(transcript: str, use_org_memory: bool, threshold: int) -> bool:
    tokens = max(len(transcript.split()), 1)
    return use_org_memory or tokens > threshold
