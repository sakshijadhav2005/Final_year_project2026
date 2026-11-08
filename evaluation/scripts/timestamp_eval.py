"""How far off are the provenance "Play from" times? (live STT + offline simulation)

Ground truth: each talk is transcribed live in short windows (default 15 s, split at
quiet points by the app's own chunker). The first word of every short chunk then has a
known time: where speech starts in that chunk (first non-quiet 100 ms frame).

Simulation: consecutive short chunks are grouped into app-sized STT chunks (300 s,
120 s, 60 s). Inside a group the app knows only the group's start/end, its word count
and (with speech spans) where the speech is. For every short-chunk boundary inside a
group we predict the boundary word's time with the app's `_time_at` (even spread vs
speech time) and compare it with the ground truth.

Assumes the long-chunk transcript has the same words as the concatenated short chunks;
in practice they differ by a few words at chunk edges.

    python evaluation/scripts/timestamp_eval.py              # all talks
    python evaluation/scripts/timestamp_eval.py --talks Al_Gore Barry_Schwartz
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics

import harness

SHORT_SECONDS = 15
GROUP_SECONDS = (300, 120, 60)


async def transcribe_short(talk: str, window: int, concurrency: int) -> dict:
    """Live: short-window transcription of one talk, cached under results/timing/."""
    path = harness.RESULTS / "timing" / f"{talk}__{window}s.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    from google.genai import types

    from app.core.config import get_settings
    from app.providers.vertex_llm import _client
    from app.providers.vertex_stt import PROMPT, _chunks

    settings = get_settings()
    model = settings.vertex_stt_model or settings.gemini_model_analyze
    chunks = await asyncio.to_thread(_chunks, str(harness.EVAL / "data" / "audio" / f"{talk}.wav"), window)
    client = _client()
    gate = asyncio.Semaphore(concurrency)

    async def one(data: bytes, mime: str) -> str:
        async with gate:
            for attempt in range(4):
                try:
                    response = await asyncio.wait_for(
                        client.aio.models.generate_content(
                            model=model,
                            contents=[PROMPT, types.Part.from_bytes(data=data, mime_type=mime)],
                            config=types.GenerateContentConfig(temperature=0.0),
                        ),
                        timeout=60,
                    )
                    return (response.text or "").strip()
                except Exception:
                    if attempt == 3:
                        raise
                    await asyncio.sleep(2 ** attempt * 2)
        return ""

    texts = await asyncio.gather(*(one(data, mime) for data, mime, *_ in chunks))
    record = {
        "talk_id": talk,
        "stt_model": model,
        "window_seconds": window,
        "config": harness.config_snapshot(),
        "chunks": [
            {"start": start, "end": end, "speech": spans, "words": len(text.split()), "text": text}
            for text, (_, _, start, end, spans) in zip(texts, chunks, strict=True)
        ],
    }
    harness.save_json(path, record)
    return record


def boundary_errors(chunks: list[dict], group_seconds: int) -> dict[str, list[float]]:
    """Errors (s) at every short-chunk boundary inside simulated app-sized chunks."""
    from app.services.provenance import _time_at

    errors: dict[str, list[float]] = {"even": [], "speech": []}
    groups: list[list[dict]] = []
    for chunk in chunks:
        if groups and chunk["end"] - groups[-1][0]["start"] <= group_seconds:
            groups[-1].append(chunk)
        else:
            groups.append([chunk])
    for group in groups:
        start, end = group[0]["start"], group[-1]["end"]
        total = sum(c["words"] for c in group)
        spans = [tuple(s) for c in group for s in (c["speech"] or [])]
        seen = 0
        for chunk in group:
            if seen and chunk["words"] and chunk["speech"]:
                truth = chunk["speech"][0][0]
                fraction = seen / total
                errors["even"].append(abs(_time_at(fraction, start, end, []) - truth))
                errors["speech"].append(abs(_time_at(fraction, start, end, spans) - truth))
            seen += chunk["words"]
    return errors


def stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(values),
        "median_s": round(statistics.median(values), 2),
        "mean_s": round(statistics.fmean(values), 2),
        "p90_s": round(ordered[int(0.9 * (len(ordered) - 1))], 2),
        "within_5s": round(sum(v <= 5 for v in values) / len(values), 3),
    }


async def main(talks: list[str], window: int, concurrency: int) -> None:
    records = []
    for talk in talks:
        try:
            records.append(await transcribe_short(talk, window, concurrency))
            print(f"{talk}: {len(records[-1]['chunks'])} short chunks", flush=True)
        except Exception as exc:  # recorded, not hidden
            print(f"{talk}: FAILED {type(exc).__name__}: {str(exc)[:200]}", flush=True)

    summary = {"window_seconds": window, "talks": [r["talk_id"] for r in records], "results": []}
    print(f"\n{'chunk':>6} {'method':>7} {'n':>5} {'median':>7} {'mean':>6} {'p90':>6} {'<=5s':>6}")
    for group_seconds in GROUP_SECONDS:
        pooled: dict[str, list[float]] = {"even": [], "speech": []}
        for record in records:
            for method, values in boundary_errors(record["chunks"], group_seconds).items():
                pooled[method].extend(values)
        for method, values in pooled.items():
            row = {"chunk_seconds": group_seconds, "method": method, **stats(values)}
            summary["results"].append(row)
            if row["n"]:
                print(f"{group_seconds:>5}s {method:>7} {row['n']:>5} {row['median_s']:>6}s "
                      f"{row['mean_s']:>5}s {row['p90_s']:>5}s {row['within_5s']:>6.0%}")
    harness.save_json(harness.RESULTS / "timing_summary.json", summary)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--talks", nargs="*")
    ap.add_argument("--window", type=int, default=SHORT_SECONDS)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    harness.configure_env("timing")
    harness.install()
    manifest = list(csv.DictReader(open(harness.EVAL / "data" / "manifest.csv")))
    talks = args.talks or [r["talk_id"] for r in manifest if float(r["duration_sec"]) >= 60]
    asyncio.run(main(talks, args.window, args.concurrency))
