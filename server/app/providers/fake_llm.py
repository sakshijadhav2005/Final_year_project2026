from typing import Any

from app.providers.llm import LLMProvider


def _demo_content(task: str, transcript: str) -> dict[str, Any]:
    snippet = " ".join(transcript.split()[:40])
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
        return {"overall": "positive", "confidence": 0.74, "notes": "Constructive, forward-looking tone."}
    if task == "content_planner":
        return {
            "brief": "Draft a factual recap pack grounded only in the transcript.",
            "angles": ["what happened", "why it matters", "next step for attendees"],
        }
    if task == "generator":
        return {
            "pieces": [
                {
                    "type": "summary",
                    "title": "Session summary",
                    "body": f"This session covered: {snippet}. Key discussion stayed on turning recordings into publish-ready content.",
                },
                {
                    "type": "blog",
                    "title": "From recording to ready-to-publish content",
                    "body": (
                        f"{snippet}\n\nThe conversation focused on a practical pipeline: transcribe, "
                        "analyze with specialist agents, generate drafts, then require a human to approve."
                    ),
                },
                {
                    "type": "linkedin",
                    "title": "LinkedIn post",
                    "body": f"Just wrapped a session on intelligent event content.\n\n{snippet}\n\n#EventAI #ContentOps",
                },
                {
                    "type": "newsletter",
                    "title": "This week's event note",
                    "body": f"Hello,\n\nA short recap from our latest session:\n\n{snippet}\n\nThanks for reading.",
                },
                {
                    "type": "ig_caption",
                    "title": "Instagram caption",
                    "body": f"Session recap ✨ {snippet[:120]}…\n\n#events #behindthetalk",
                },
                {
                    "type": "flyer",
                    "title": "Event recap flyer",
                    "body": "Recap highlights from the session.",
                    "structured": {
                        "headline": "Session recap",
                        "subhead": "What was said, ready to share",
                        "bullets": ["Transcribe", "Analyze", "Generate", "Approve"],
                    },
                },
            ]
        }
    if task == "guardrail":
        return {"pass": True, "issues": []}
    if task == "translation":
        return {"text": transcript}
    return {"ok": True, "task": task}


class FakeLLMProvider(LLMProvider):
    name = "fake"

    async def generate_json(self, *, system: str, user: str, temperature: float = 0.3) -> dict[str, Any]:
        task = "unknown"
        for line in user.splitlines():
            if line.startswith("TASK="):
                task = line.split("=", 1)[1].strip()
                break
        transcript = user
        if "<untrusted_transcript>" in user:
            transcript = user.split("<untrusted_transcript>", 1)[1].split("</untrusted_transcript>", 1)[0]
        result = _demo_content(task, transcript)
        result["mock"] = True
        result["temperature"] = temperature
        result["system_ok"] = "untrusted" in system.lower()
        return result
