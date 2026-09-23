from typing import Any

from app.providers.llm import LLMProvider


def _demo_content(task: str, transcript: str) -> dict[str, Any]:
    snippet = " ".join(transcript.split()[:40]) if transcript else "Event recap content"
    if task == "topic_extraction":
        return {
            "topics": ["event recap", "AI content pipeline", "community takeaways"],
            "keywords": ["EventAI", "transcription", "publish-ready content"],
            "session_type": "talk",
        }
    if task == "highlight_detection":
        return {
            "highlights": [
                {"quote": snippet[:180], "why": "Opening framing of the session"},
            ]
        }
    if task == "speaker_analysis":
        return {
            "speakers": [{"label": "host", "role": "presenter"}],
            "notes": "Diarization not available; single-speaker assumption.",
        }
    if task == "sentiment_analysis":
        return {
            "overall": "positive",
            "confidence": 0.74,
            "notes": "Constructive, forward-looking tone.",
        }
    if task == "content_planner":
        return {
            "brief": "Draft a factual recap pack grounded only in the transcript.",
            "angles": ["what happened", "why it matters", "next step for attendees"],
        }
    if task in {"summary", "executive_summary"}:
        return {
            "type": "summary",
            "title": "Executive Session Summary",
            "body": f"This session covered: {snippet}. Key discussion stayed on turning recordings into publish-ready content.",
            "structured": {
                "bullets": [
                    "Turn recordings into insights",
                    "Grounded AI pipelines",
                    "Multi-channel syndication",
                ]
            },
        }
    if task in {"blog", "blog_post"}:
        return {
            "type": "blog",
            "title": "From Recording to Ready-to-Publish Content",
            "body": (
                f"## Overview\n{snippet}\n\n## Key Takeaways\n"
                "- Practical pipeline: transcribe and analyze with specialist agents\n"
                "- Generate drafts and verify guardrails\n"
                "- Publish directly to community catalogs."
            ),
            "structured": {"reading_time_mins": 3},
        }
    if task in {"linkedin", "linkedin_post"}:
        return {
            "type": "linkedin",
            "title": "LinkedIn Key Takeaways",
            "body": f"Just wrapped a high-impact session on intelligent event content.\n\n{snippet}\n\n#EventAI #ContentOps #PuneTech",
            "structured": {"hashtags": ["#EventAI", "#ContentOps", "#PuneTech"]},
        }
    if task in {"newsletter", "email_newsletter"}:
        return {
            "type": "newsletter",
            "title": "This Week's Event Note",
            "body": f"Hello,\n\nA short recap from our latest session:\n\n{snippet}\n\nThanks for reading.",
            "structured": {"tldr": snippet[:100]},
        }
    if task in {"instagram", "ig_caption"}:
        return {
            "type": "instagram",
            "title": "Instagram Carousel & Visual Copy",
            "body": f"Session recap ✨\n\n{snippet[:120]}…\n\nDrop your thoughts below! 👇\n\n#events #behindthetalk #punetech",
            "structured": {"slides": [snippet[:80], snippet[80:160]]},
        }
    if task in {"flyer", "event_flyer"}:
        return {
            "type": "flyer",
            "title": "Event Recap Flyer",
            "body": "Recap highlights from the session.",
            "structured": {
                "headline": "Session Recap",
                "subhead": "What was said, ready to share",
                "bullets": ["Transcribe", "Analyze", "Generate", "Approve"],
            },
        }
    if task == "generator":
        return {
            "pieces": [
                {
                    "type": "summary",
                    "title": "Session summary",
                    "body": f"This session covered: {snippet}.",
                },
                {
                    "type": "blog",
                    "title": "From recording to ready-to-publish content",
                    "body": f"{snippet}\n\nPractical pipeline recap.",
                },
                {
                    "type": "linkedin",
                    "title": "LinkedIn post",
                    "body": f"Wrapped session: {snippet}\n\n#EventAI",
                },
            ]
        }
    if task == "guardrail":
        return {"pass": True, "issues": []}
    if task == "translation":
        return {"text": transcript}
    return {"ok": True, "task": task, "title": "Session Note", "body": snippet}


class FakeLLMProvider(LLMProvider):
    name = "fake"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3
    ) -> dict[str, Any]:
        task = "unknown"
        for line in user.splitlines():
            if line.startswith("TASK="):
                task = line.split("=", 1)[1].strip()
                break
        if task == "unknown":
            for candidate in [
                "linkedin",
                "instagram",
                "newsletter",
                "blog",
                "summary",
                "flyer",
                "content_planner",
                "topic_extraction",
                "highlight_detection",
                "speaker_analysis",
                "sentiment_analysis",
            ]:
                if (
                    f"Generate the {candidate}" in user
                    or f"{candidate} copywriter" in system.lower()
                    or f"{candidate}_skill" in system.lower()
                ):
                    task = candidate
                    break

        transcript = user
        if "<untrusted_transcript>" in user:
            transcript = user.split("<untrusted_transcript>", 1)[1].split(
                "</untrusted_transcript>", 1
            )[0]
        result = _demo_content(task, transcript)
        result["mock"] = True
        result["temperature"] = temperature
        result["system_ok"] = "untrusted" in system.lower()
        return result
