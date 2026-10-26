"""Live runs of the real EventAI backend on TED-LIUM talks (in-process ASGI client).

For each talk:
  1. e2e     - register, upload the WAV through POST /api/v1/uploads; the background
               job runs the full pipeline (media check, STT, analysis, planner, RAG,
               6 writer agents, guardrail, Hindi translation). RAG on (app default).
  2. regen   - (long talks only, --ablation) POST /jobs/{id}/regenerate reuses the
               stored transcript; alternating RAG on / RAG off, --repeats times each.

    python evaluation/scripts/run_pipeline.py --worker w1 --talks Al_Gore Brian_Cox --ablation 3
"""

from __future__ import annotations

import argparse
import time
import uuid
from datetime import UTC, datetime

import harness

TYPES = "summary,blog,linkedin,newsletter,instagram,flyer"
LANGS = "en,hi"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", required=True)
    ap.add_argument("--talks", nargs="+", required=True)
    ap.add_argument("--ablation", type=int, default=0, help="repeats per RAG condition")
    args = ap.parse_args()

    harness.configure_env(args.worker)
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import app

    harness.install()
    settings = get_settings()
    audio = harness.EVAL / "data" / "audio"
    out_dir = harness.RESULTS / "raw"

    with TestClient(app) as client:
        email = f"eval_{args.worker}_{uuid.uuid4().hex[:6]}@example.com"
        res = client.post("/api/v1/auth/register",
                          json={"email": email, "password": "password123", "role": "event_organizer"})
        res.raise_for_status()
        headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        # A neutral organiser profile (real users fill this in Settings); without one the
        # writers sign posts with the placeholder persona "Event Speaker".
        client.put("/api/v1/auth/profile", headers=headers, json={
            "full_name": "EventAI Research Team", "organization": "EventAI",
            "job_title": "Content Team",
        }).raise_for_status()

        def collect(job_id: str) -> dict:
            job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
            transcript = client.get(f"/api/v1/jobs/{job_id}/transcript", headers=headers).json()
            content = client.get(f"/api/v1/jobs/{job_id}/content", headers=headers).json()
            return {"job": job, "transcript": transcript, "content": content}

        db_file = settings.database_url.split("///")[-1]

        def agent_outputs(job_id: str, since: datetime) -> dict:
            """Read-only sqlite3 query (the app's async engine belongs to the client's loop).
            created_at is SQLite CURRENT_TIMESTAMP (UTC, 1 s resolution)."""
            import json
            import sqlite3

            con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            try:
                rows = con.execute(
                    "SELECT agent_name, payload, created_at FROM agent_outputs "
                    "WHERE job_id = ? AND created_at >= ? ORDER BY created_at",
                    (uuid.UUID(job_id).hex, since.strftime("%Y-%m-%d %H:%M:%S")),
                ).fetchall()
            finally:
                con.close()
            return {name: json.loads(payload) for name, payload, _ in rows}

        def record(talk, mode, condition, repeat, job_id, wall, since):
            data = collect(job_id)
            run = {
                "run_id": f"{talk}__{mode}__{condition}__{repeat}",
                "talk_id": talk, "mode": mode, "condition": condition, "repeat": repeat,
                "job_id": job_id, "wall_sec": wall,
                "started_utc": since.isoformat(),
                "config": harness.config_snapshot(),
                "stages": list(harness.STAGES), "calls": list(harness.CALLS),
                "agent_outputs": agent_outputs(job_id, since),
                **data,
            }
            harness.save_json(out_dir / f"{run['run_id']}.json", run)
            gen = [c for c in run["calls"] if c["kind"] == "llm"]
            print(f"[{args.worker}] {run['run_id']}: status={data['job'].get('status')} "
                  f"wall={wall:.1f}s llm_calls={len(gen)} pieces={len(data['content'] or [])}", flush=True)
            return run

        for talk in args.talks:
            # 1. Full end-to-end run from audio.
            settings.rag_enabled = True
            harness.reset()
            since = datetime.now(UTC)
            t0 = time.perf_counter()
            with (audio / f"{talk}.wav").open("rb") as fh:
                res = client.post(
                    "/api/v1/uploads", headers=headers,
                    files={"file": (f"{talk}.wav", fh, "audio/wav")},
                    data={"consent_confirmed": "true", "requested_types": TYPES, "target_languages": LANGS},
                )
            wall = time.perf_counter() - t0  # TestClient returns after the background job finishes
            if res.status_code != 202:
                print(f"[{args.worker}] {talk}: upload failed {res.status_code} {res.text[:200]}", flush=True)
                continue
            job_id = res.json()["id"]
            run = record(talk, "e2e", "rag_on", 0, job_id, wall, since)

            words = len(((run.get("transcript") or {}).get("full_text") or "").split())
            if not args.ablation or words <= settings.rag_token_threshold:
                continue

            # 2. RAG ablation on the same stored transcript, conditions interleaved.
            for rep in range(1, args.ablation + 1):
                for condition in ("rag_on", "rag_off"):
                    settings.rag_enabled = condition == "rag_on"
                    harness.reset()
                    since = datetime.now(UTC)
                    t0 = time.perf_counter()
                    res = client.post(f"/api/v1/jobs/{job_id}/regenerate", headers=headers, json={})
                    wall = time.perf_counter() - t0
                    if res.status_code != 202:
                        print(f"[{args.worker}] regen failed {res.status_code} {res.text[:200]}", flush=True)
                        continue
                    record(talk, "regen", condition, rep, job_id, wall, since)
            settings.rag_enabled = True


if __name__ == "__main__":
    main()
