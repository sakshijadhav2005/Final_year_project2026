from __future__ import annotations

import re
from typing import Any

from app.providers.llm import LLMProvider


def _clean_transcript(text: str) -> str:
    if "<untrusted_transcript>" in text:
        text = text.split("<untrusted_transcript>", 1)[1].split("</untrusted_transcript>", 1)[0]
    elif "<TRANSCRIPT>" in text:
        text = text.split("<TRANSCRIPT>", 1)[1].split("</TRANSCRIPT>", 1)[0]
    return text.strip()


def _extract_sentences(text: str) -> list[str]:
    raw = _clean_transcript(text)
    # Split into clean meaningful sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", raw) if len(s.strip()) > 15]
    if not sentences and raw:
        sentences = [raw]
    return sentences


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"\b[A-Za-z]{4,}\b", _clean_transcript(text))
    freq: dict[str, int] = {}
    stopwords = {
        "this", "that", "with", "from", "have", "were", "what", "when", "your", "more",
        "they", "them", "then", "there", "about", "which", "will", "would", "these",
        "could", "should", "some", "other", "into", "also", "most", "than"
    }
    for w in words:
        wl = w.lower()
        if wl not in stopwords:
            freq[w.capitalize()] = freq.get(w.capitalize(), 0) + 1
    sorted_words = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)
    return sorted_words[:8] if sorted_words else ["Technology", "Engineering", "Innovation"]


def _demo_content(task: str, raw_text: str) -> dict[str, Any]:
    transcript = _clean_transcript(raw_text)
    sentences = _extract_sentences(transcript)
    keywords = _extract_keywords(transcript)

    first_sentence = sentences[0] if sentences else "Key takeaways from today's session."
    main_points = sentences[:4] if len(sentences) >= 4 else sentences
    bullets = [f"• {s}" for s in main_points] if main_points else [f"• {first_sentence}"]
    topic_headline = " & ".join(keywords[:2]) if len(keywords) >= 2 else "Session Recap"

    if task == "topic_extraction":
        return {
            "topics": keywords[:5],
            "keywords": [f"#{k}" for k in keywords[:6]],
            "session_type": "Workshop & Keynote",
        }

    if task == "highlight_detection":
        return {
            "highlights": [
                {"quote": s, "why": "Core concept emphasized in the session"}
                for s in sentences[:3]
            ]
        }

    if task == "speaker_analysis":
        return {
            "speakers": [{"label": "Speaker", "role": "Presenter"}],
            "notes": f"Main discussion focused on: {topic_headline}.",
        }

    if task == "sentiment_analysis":
        return {
            "overall": "constructive & insightful",
            "confidence": 0.88,
            "notes": "Direct, actionable, and solution-oriented discussion.",
        }

    if task == "content_planner":
        return {
            "brief": f"Recap covering {topic_headline} grounded strictly in the session transcript.",
            "angles": [
                "Key takeaways and core concepts",
                "Actionable technical insights",
                "Next steps for implementation",
            ],
        }

    if task in {"summary", "executive_summary"}:
        body_text = "\n\n".join(sentences[:3]) if sentences else transcript[:300]
        return {
            "type": "summary",
            "title": f"Executive Summary: {topic_headline}",
            "body": f"## Overview\n{body_text}\n\n### Key Takeaways\n" + "\n".join(bullets),
            "structured": {
                "bullets": [s.lstrip("• ") for s in bullets],
                "topics": keywords[:4],
            },
        }

    if task in {"blog", "blog_post"}:
        body_sections = [
            f"## Introduction\n{first_sentence}",
            "## Core Discussion & Insights\n" + "\n\n".join(sentences[1:4] if len(sentences) > 1 else sentences),
            "## Key Takeaways\n" + "\n".join(bullets),
            f"## Conclusion\nThe session provided clear guidance on {topic_headline}. Applying these practices helps teams build scalable, reliable solutions."
        ]
        return {
            "type": "blog",
            "title": f"Deep Dive: Mastering {topic_headline}",
            "body": "\n\n".join(body_sections),
            "structured": {"reading_time_mins": max(2, len(transcript.split()) // 150)},
        }

    if task in {"linkedin", "linkedin_post"}:
        hashtags = " ".join([f"#{k.replace(' ', '')}" for k in keywords[:5]])
        linkedin_body = (
            f"🚀 Key insights from our session on {topic_headline}:\n\n"
            f"{first_sentence}\n\n"
            "Key takeaways for engineers and builders:\n"
            f"{chr(10).join(bullets)}\n\n"
            "How is your team approaching these challenges in production? Let's discuss below 👇\n\n"
            f"{hashtags}"
        )
        return {
            "type": "linkedin",
            "title": f"{topic_headline}: Key Lessons & Takeaways",
            "body": linkedin_body,
            "structured": {"hashtags": [f"#{k.replace(' ', '')}" for k in keywords[:5]]},
        }

    if task in {"newsletter", "email_newsletter"}:
        newsletter_body = (
            f"# {topic_headline} — Session Digest\n\n"
            "Hello,\n\n"
            f"Here is your executive recap of our recent discussion:\n\n"
            f"> \"{first_sentence}\"\n\n"
            "### Highlights:\n"
            f"{chr(10).join(bullets)}\n\n"
            "Stay tuned for our upcoming workshops and updates."
        )
        return {
            "type": "newsletter",
            "title": f"Newsletter: {topic_headline} Recap",
            "body": newsletter_body,
            "structured": {"tldr": first_sentence},
        }

    if task in {"instagram", "ig_caption"}:
        ig_hashtags = " ".join([f"#{k.lower()}" for k in keywords[:6]])
        ig_body = (
            f"✨ Insights on {topic_headline} ✨\n\n"
            f"{first_sentence}\n\n"
            "📌 Quick highlights:\n"
            f"{chr(10).join(bullets[:3])}\n\n"
            f"💾 Save this post for later!\n\n"
            f"{ig_hashtags}"
        )
        return {
            "type": "instagram",
            "title": f"Instagram Carousel: {topic_headline}",
            "body": ig_body,
            "structured": {"visual_prompt": f"Modern infographic banner for {topic_headline}"},
        }

    if task in {"flyer", "marketing_flyer"}:
        flyer_body = (
            f"# 📢 {topic_headline}\n\n"
            f"**Key Theme:** {first_sentence}\n\n"
            "### What You Need To Know:\n"
            f"{chr(10).join(bullets[:3])}\n\n"
            "**Organized by Tech Community** | Share with your network"
        )
        return {
            "type": "flyer",
            "title": f"Event Flyer: {topic_headline}",
            "body": flyer_body,
            "structured": {"theme": topic_headline},
        }

    if task == "guardrail":
        return {"pass": True, "issues": []}

    if task in {"guardrail_batch", "translation_batch"}:
        import json as _json

        m = re.search(r"<DRAFTS_JSON>\s*([\s\S]*?)\s*</DRAFTS_JSON>", raw_text)
        try:
            drafts = _json.loads(m.group(1)) if m else {}
        except ValueError:
            drafts = {}
        if task == "guardrail_batch":
            return {
                "results": {
                    k: {"grounding_pass": True, "moderation_pass": True, "issues": []} for k in drafts
                }
            }
        # Offline mode has no translator: return the drafts unchanged.
        return {"drafts": drafts}

    if task == "translation":
        # Extract title and body from prompt
        title_match = re.search(r"Title=([^\n]+)", raw_text)
        title = title_match.group(1).strip() if title_match else f"{topic_headline} (Recap)"
        body_match = re.search(r"Body=([\s\S]+)", raw_text)
        body = body_match.group(1).strip() if body_match else "\n\n".join(bullets)
        return {
            "title": title,
            "body": body,
        }

    return {
        "ok": True,
        "task": task,
        "title": f"{topic_headline} Overview",
        "body": "\n\n".join(bullets) if bullets else transcript[:400],
    }


class FakeLLMProvider(LLMProvider):
    name = "fake"

    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3, fast: bool = False
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
                if candidate in user.lower() or candidate in system.lower():
                    task = candidate
                    break

        result = _demo_content(task, user)
        result["mock"] = True
        result["temperature"] = temperature
        result["system_ok"] = True
        return result
