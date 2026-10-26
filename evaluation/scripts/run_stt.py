"""STT-only runs (cached-stage experiment): the app's transcribe_file() with the Vertex
STT provider, varying the Gemini model and the chunk length.

    python evaluation/scripts/run_stt.py --models gemini-3.6-flash gemini-3.7-flash --chunks 300
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import time

import harness


async def main(models: list[str], chunks: list[int], talks: list[str]) -> None:
    from app.core.config import get_settings
    from app.services.transcription import transcribe_file

    settings = get_settings()
    audio = harness.EVAL / "data" / "audio"
    out = harness.RESULTS / "stt"
    for model in models:
        for chunk in chunks:
            for talk in talks:
                path = out / f"{talk}__{model}__{chunk}s.json"
                if path.exists():
                    continue
                settings.vertex_stt_model = model
                settings.stt_chunk_seconds = chunk
                harness.reset()
                token = harness.STAGE.set("stt")
                t0 = time.perf_counter()
                try:
                    result = await transcribe_file(str(audio / f"{talk}.wav"))
                    error = None
                except Exception as exc:  # recorded, not hidden
                    result, error = None, f"{type(exc).__name__}: {str(exc)[:300]}"
                t1 = time.perf_counter()
                harness.STAGE.reset(token)
                harness.save_json(path, {
                    "talk_id": talk, "stt_model": model, "chunk_seconds": chunk,
                    "error": error, "config": harness.config_snapshot(),
                    "stages": [{"stage": "stt", "t0": t0, "t1": t1, "agent": None}],
                    "calls": list(harness.CALLS),
                    "transcript": {"full_text": result.text if result else "",
                                   "provider": result.provider if result else None},
                })
                print(f"{talk} {model} {chunk}s: {t1 - t0:.1f}s {error or ''}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--chunks", nargs="+", type=int, default=[300])
    args = ap.parse_args()
    harness.configure_env("stt")
    harness.install()
    manifest = list(csv.DictReader(open(harness.EVAL / "data" / "manifest.csv")))
    talks = [r["talk_id"] for r in manifest if float(r["duration_sec"]) >= 60]
    asyncio.run(main(args.models, args.chunks, talks))
