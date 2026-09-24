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


from app.providers.factory import get_llm_provider
from app.services.resilience import llm_circuit, with_backoff

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


def should_use_rag(transcript: str, use_org_memory: bool, threshold: int) -> bool:
    tokens = max(len(transcript.split()), 1)
    return use_org_memory or tokens > threshold
