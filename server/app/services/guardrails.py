import re

from app.providers.factory import get_llm_provider
from app.services.resilience import llm_circuit, with_backoff

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



async def verify_content_with_llm(body: str, transcript: str) -> dict:
    """Uses LLM-as-a-judge to semantically verify facts and screen for moderation."""
    llm = get_llm_provider()
    
    system_prompt = (
        "You are an elite fact-checker and moderation guardrail. "
        "Read the provided 'Generated Post' and cross-reference it against the 'Original Transcript'. "
        "1. Check if the post hallucinates or invents claims not present in the transcript. "
        "2. Check if the post contains toxic, profane, or explicitly harmful content. "
        "Return JSON exactly in this format: "
        '{"grounding_pass": true/false, "moderation_pass": true/false, "issues": ["list of hallucinated or toxic quotes if any"]}'
    )
    
    user_prompt = f"Original Transcript:\n{transcript[:12000]}\n\nGenerated Post:\n{body}"
    
    async def _call():
        return await llm.generate_json(system=system_prompt, user=user_prompt, temperature=0.1)

    try:
        res = await with_backoff(_call, circuit=llm_circuit)
        
        # Fallback parsing in case the LLM didn't return exactly true/false
        g_pass = res.get("grounding_pass", True)
        m_pass = res.get("moderation_pass", True)
        issues = res.get("issues", [])
        
        return {
            "grounding": {"pass": g_pass, "issues": issues},
            "moderation": {"pass": m_pass, "hits": issues if not m_pass else []}
        }
    except Exception as e:
        # If API fails, default to pass so we don't break the pipeline completely
        return {
            "grounding": {"pass": True, "issues": [str(e)]},
            "moderation": {"pass": True, "hits": []}
        }


GUARDRAIL_TRANSCRIPT_CHARS = 300_000  # whole talk: writers also use RAG excerpts from later parts


async def verify_batch_with_llm(
    pieces: list[dict], transcript: str, author_profile: dict | None = None
) -> dict[str, dict]:
    """One LLM-as-a-judge call for ALL drafts (instead of one call per draft).

    Returns {content_type: {"grounding": {...}, "moderation": {...}}}. Any draft the
    judge does not return a verdict for falls back to the fast local checks, so a
    malformed reply never blocks the pipeline.
    """
    import json

    llm = get_llm_provider()
    drafts = {
        str(p.get("type")): {"title": p.get("title") or "", "body": str(p.get("body") or "")[:6000]}
        for p in pieces
    }
    system_prompt = (
        "You are an elite fact-checker and moderation guardrail. For EACH draft, check "
        "(1) whether it invents claims not present in the transcript and (2) whether it "
        "contains toxic, profane or harmful content. Reply with JSON only, exactly: "
        '{"results": {"<draft_type>": {"grounding_pass": true/false, '
        '"moderation_pass": true/false, "issues": ["short quote of any problem"]}}}. '
        "Author and brand details listed in AUTHOR_PROFILE were supplied by the user for "
        "sign-offs and attribution; they are not invented claims."
    )
    profile = {k: v for k, v in (author_profile or {}).items() if v}
    user_prompt = (
        "TASK=guardrail_batch\n"
        f"<AUTHOR_PROFILE>\n{json.dumps(profile, ensure_ascii=False)}\n</AUTHOR_PROFILE>\n\n"
        f"<TRANSCRIPT>\n{transcript[:GUARDRAIL_TRANSCRIPT_CHARS]}\n</TRANSCRIPT>\n\n"
        f"<DRAFTS_JSON>\n{json.dumps(drafts, ensure_ascii=False)}\n</DRAFTS_JSON>"
    )

    verdicts: dict = {}
    try:
        res = await with_backoff(
            lambda: llm.generate_json(system=system_prompt, user=user_prompt, temperature=0.1, fast=True),
            circuit=llm_circuit,
            attempts=2,
        )
        verdicts = res.get("results") if isinstance(res.get("results"), dict) else {}
    except Exception:
        verdicts = {}

    out: dict[str, dict] = {}
    for ctype, draft in drafts.items():
        v = verdicts.get(ctype)
        if isinstance(v, dict):
            issues = v.get("issues") or []
            m_pass = bool(v.get("moderation_pass", True))
            out[ctype] = {
                "grounding": {"pass": bool(v.get("grounding_pass", True)), "issues": issues},
                "moderation": {"pass": m_pass, "hits": issues if not m_pass else []},
            }
        else:  # no verdict: cheap local checks, no extra API call
            out[ctype] = {
                "grounding": grounding_check(draft["body"], transcript),
                "moderation": moderate_text(draft["body"]),
            }
    return out


def should_use_rag(transcript: str, use_org_memory: bool, threshold: int) -> bool:
    tokens = max(len(transcript.split()), 1)
    return use_org_memory or tokens > threshold
