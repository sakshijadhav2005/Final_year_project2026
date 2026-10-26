"""Generated-content quality: LLM-as-judge rubric + key-point coverage (automatic judge).

Ground truth is the TED-LIUM 3 HUMAN reference transcript, never the system's own ASR
output. Judge: gemini-3.7-flash (a different, larger model than the system's
gemini-3.1-flash-lite), temperature 0, blind to the experimental condition.

1. Key points: per talk, the judge lists 10 key points from the reference transcript,
   each with a verbatim quote. A point's position in the talk is the quote's character
   offset / reference length (computed mechanically; points whose quote is not found
   verbatim are dropped). A point is "late" when it lies beyond the share of the talk
   the writer agents see directly (12,000 characters of the ASR transcript).
2. Per run: ONE judge call scores the six English drafts on a 1-5 rubric (factual
   consistency, relevance, completeness, readability, instruction adherence), lists
   unsupported claims and marks which key points each draft covers.

    python evaluation/scripts/judge_quality.py                 # primary judge, all runs
    python evaluation/scripts/judge_quality.py --second-judge  # agreement subset (e2e runs)
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import re

import harness

JUDGE = "gemini-3.7-flash"
SECOND_JUDGE = "gemini-3.6-flash"
AGENT_CHARS = 12000
DIMENSIONS = ["factual_consistency", "relevance", "completeness", "readability", "instruction_adherence"]

FORMAT_SPECS = {
    "summary": "Executive summary/briefing: TL;DR, key evidence, discussion points, action items; under 400 words; Markdown.",
    "blog": "Long-form article in Markdown with an engaging title, introduction, numbered sections with insights, a comparison/takeaway table, conclusion and an 'About the Author' section.",
    "linkedin": "LinkedIn post: hook, short story/insights in short paragraphs, a question or call to action, 3-5 relevant hashtags; no cliches like 'I am thrilled to share' and no filler words like 'delve', 'game-changer'.",
    "newsletter": "Email newsletter: subject line under 50 characters, greeting, three sections with bold subheadings, call to action; conversational and editorial.",
    "instagram": "Instagram caption: hook, carousel/visual cues, short lines with emojis, call to action, 10-15 targeted hashtags.",
    "flyer": "Event flyer/poster copy: bold title of at most 6 words, short high-impact lines, highlights; logistics (date, venue, registration) only if known, otherwise 'TBA'.",
}

RUBRIC = """Score each draft from 1 (very poor) to 5 (excellent) on:
- factual_consistency: every claim about the talk is supported by the reference transcript (5 = no unsupported claims; author/brand details from the AUTHOR_PROFILE and 'TBA' placeholders are acceptable).
- relevance: content is about the talk's actual subject and main messages.
- completeness: covers the talk's important points appropriately for the format's length.
- readability: clear, well organised, fluent, appropriate tone.
- instruction_adherence: follows the FORMAT REQUIREMENTS for its type.
Also list `unsupported_claims` (short quotes of claims not supported by the transcript) and
`covered_key_points` (ids of KEY_POINTS the draft clearly conveys)."""


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", text.lower()).split())


async def _json_call(client, model: str, prompt: str) -> dict:
    from google.genai import types

    for attempt in range(4):
        try:
            resp = await asyncio.wait_for(client.aio.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"),
            ), timeout=300)
            return json.loads(resp.text)
        except Exception as exc:  # transient quota / malformed JSON: retry, then give up loudly
            if attempt == 3:
                raise
            print(f"  retry {attempt + 1} after {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            await asyncio.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


async def key_points(client, talk: str, ref: str) -> list[dict]:
    path = harness.RESULTS / "judge" / "key_points" / f"{talk}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = await _json_call(client, JUDGE, (
        "List the 10 most important key points of this talk, spread over the whole talk. For each give "
        "`point` (one sentence) and `quote` (an exact, contiguous, verbatim copy of 8-25 words from the "
        'transcript that states it). Reply as JSON {"items": [{"point": "...", "quote": "..."}]}\n\n'
        f"<TRANSCRIPT>\n{ref}\n</TRANSCRIPT>"
    ))
    nref = norm(ref)
    points = []
    for item in data.get("items", []):
        q = norm(item.get("quote", ""))
        pos = nref.find(q) if len(q.split()) >= 6 else -1
        if pos >= 0:
            points.append({"id": len(points) + 1, "point": item["point"], "quote": item["quote"],
                           "position": round(pos / len(nref), 4)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(points, indent=1, ensure_ascii=False), encoding="utf-8")
    return points


async def judge_run(client, model: str, run: dict, ref: str, points: list[dict], out_dir) -> None:
    path = out_dir / f"{run['run_id']}.json"
    if path.exists():
        return
    drafts = {p["type"]: {"title": p.get("title") or "", "body": p.get("body") or ""}
              for p in run.get("content") or [] if p.get("language") == "en"}
    if not drafts:
        return
    prompt = (
        "You are an expert editor evaluating AI-generated marketing content about a recorded talk "
        "against the talk's human reference transcript.\n\n" + RUBRIC + "\n\n"
        "FORMAT REQUIREMENTS:\n" + "\n".join(f"- {t}: {FORMAT_SPECS[t]}" for t in drafts if t in FORMAT_SPECS) + "\n\n"
        '<AUTHOR_PROFILE>{"full_name": "EventAI Research Team", "organization": "EventAI", "job_title": "Content Team"}</AUTHOR_PROFILE>\n\n'
        "<KEY_POINTS>\n" + "\n".join(f"{p['id']}. {p['point']}" for p in points) + "\n</KEY_POINTS>\n\n"
        f"<REFERENCE_TRANSCRIPT>\n{ref}\n</REFERENCE_TRANSCRIPT>\n\n"
        f"<DRAFTS_JSON>\n{json.dumps(drafts, ensure_ascii=False)}\n</DRAFTS_JSON>\n\n"
        'Reply as JSON: {"drafts": {"<type>": {"factual_consistency": n, "relevance": n, "completeness": n, '
        '"readability": n, "instruction_adherence": n, "unsupported_claims": ["..."], '
        '"covered_key_points": [ids], "justification": "one sentence"}}}'
    )
    data = await _json_call(client, model, prompt)
    harness.save_json(path, {"run_id": run["run_id"], "judge_model": model, "talk_id": run["talk_id"],
                             "mode": run["mode"], "condition": run["condition"], "repeat": run["repeat"],
                             "verdicts": data.get("drafts", {})})
    print(f"  judged {run['run_id']} ({model})", flush=True)


async def main(second: bool) -> None:
    from app.providers.vertex_llm import _client

    client = _client()
    model = SECOND_JUDGE if second else JUDGE
    out_dir = harness.RESULTS / ("judge2" if second else "judge") / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = "*__e2e__*.json" if second else "*.json"
    runs = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(str(harness.RESULTS / "raw" / pattern)))]
    refs = {}
    for t in {r["talk_id"] for r in runs}:
        refs[t] = " ".join((harness.EVAL / "data" / "references" / f"{t}.txt").read_text(encoding="utf-8").replace("<unk>", " ").split())
    points = {t: await key_points(client, t, refs[t]) for t in sorted(refs)}
    gate = asyncio.Semaphore(4)

    async def one(run):
        async with gate:
            try:
                await judge_run(client, model, run, refs[run["talk_id"]], points[run["talk_id"]], out_dir)
            except Exception as exc:
                print(f"  FAILED {run['run_id']}: {type(exc).__name__}: {str(exc)[:200]}", flush=True)

    await asyncio.gather(*(one(r) for r in runs))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--second-judge", action="store_true")
    args = ap.parse_args()
    harness.configure_env("judge")
    asyncio.run(main(args.second_judge))
