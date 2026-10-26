"""Mock-based reliability experiment (no network).

Runs the production VertexLLMProvider (model fallback chain, transient-error retry,
offline fallback) and the production retry/circuit-breaker code against a fake Vertex
client that injects one failure type per scenario. Real sleeps from the retry policy
are kept, so recovery latency is measured, not simulated.

    python evaluation/scripts/fault_injection.py --trials 20
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import time

import harness

PRIMARY = "gemini-3.1-flash-lite"
GOOD_JSON = '{"title": "ok", "body": "grounded draft"}'


class _Resp:
    def __init__(self, text: str):
        self.text = text


class FakeModels:
    """behaviour(model, n) -> text or raises; n = how many times this model was called."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls: list[str] = []

    async def generate_content(self, *, model, contents, config=None):
        self.calls.append(model)
        return _Resp(self.behaviour(model, self.calls.count(model)))


class FakeClient:
    def __init__(self, behaviour):
        self.models = FakeModels(behaviour)
        self.aio = self


def err(code: int, msg: str) -> Exception:
    return RuntimeError(f"{code} {msg}")


def primary_then_ok(fail):
    def b(model, n):
        if model == PRIMARY and n == 1:
            raise fail
        return GOOD_JSON
    return b


def primary_always(fail=None, text=None):
    def b(model, n):
        if model == PRIMARY:
            if fail:
                raise fail
            return text
        return GOOD_JSON
    return b


def all_fail(model, n):
    raise err(500, "INTERNAL")


SCENARIOS = {
    "S0 no fault": lambda m, n: GOOD_JSON,
    "S1 transient 429 (once)": primary_then_ok(err(429, "RESOURCE_EXHAUSTED")),
    "S2 timeout (once)": primary_then_ok(TimeoutError("deadline exceeded")),
    "S3 persistent 429 on primary": primary_always(fail=err(429, "RESOURCE_EXHAUSTED")),
    "S4 model 404 not found": primary_always(fail=err(404, "NOT_FOUND model")),
    "S5 empty response": primary_always(text=""),
    "S6 JSON in markdown fence": lambda m, n: "```json\n" + GOOD_JSON + "\n```",
    "S7 prose, no JSON": lambda m, n: "Sure! Here is your post: great talk.",
    "S8 all models 500": all_fail,
}


async def trial(name, behaviour) -> dict:
    import app.providers.vertex_llm as vl
    from app.core.config import get_settings
    from app.providers.vertex_llm import VertexLLMProvider
    from app.services import degraded
    from app.services.resilience import llm_circuit

    harness.reset()
    llm_circuit.reset()
    events = degraded.start()
    settings = get_settings()
    fake = FakeClient(behaviour)
    vl._CLIENTS.clear()
    vl._CLIENTS[(settings.google_cloud_project, settings.google_cloud_location)] = fake
    t0 = time.perf_counter()
    out = await VertexLLMProvider().generate_json(system="s", user="u")
    sec = time.perf_counter() - t0
    calls = fake.models.calls
    last = calls[-1] if calls else None
    if out.get("title") == "ok":
        outcome = "primary model" if last == PRIMARY else "fallback model"
    elif "raw" in out:
        outcome = "unparsed (raw text)"
    else:
        outcome = "offline template"
    flagged = bool(events)
    # A second call in the same process shows whether the provider remembers the outcome.
    calls_before = len(calls)
    await VertexLLMProvider().generate_json(system="s", user="u")
    return {
        "scenario": name, "outcome": outcome, "attempts": calls_before,
        "models_tried": "|".join(dict.fromkeys(calls[:calls_before])),
        "latency_sec": round(sec, 3), "degraded_flagged": flagged,
        "second_call_model": calls[calls_before] if len(calls) > calls_before else None,
    }


async def circuit_probe(failures: int = 8) -> dict:
    """Does the circuit breaker short-circuit calls after repeated failures?"""
    from app.services.resilience import llm_circuit, with_backoff

    llm_circuit.reset()
    invoked = 0

    async def boom():
        nonlocal invoked
        invoked += 1
        raise err(500, "INTERNAL")

    blocked = 0
    for _ in range(failures):
        try:
            await with_backoff(boom, circuit=llm_circuit, attempts=1)
        except Exception as exc:
            if type(exc).__name__ == "CircuitOpenError":
                blocked += 1
    return {"consecutive_failing_calls": failures, "fail_max": llm_circuit.fail_max,
            "upstream_invocations": invoked, "short_circuited": blocked,
            "breaker_open_until_set": llm_circuit.open_until > 0}


async def sustained_probe(calls: int = 8) -> dict:
    """Primary model keeps returning 429: which calls still try it (per-model breaker)?"""
    import app.providers.vertex_llm as vl
    from app.core.config import get_settings
    from app.providers.vertex_llm import VertexLLMProvider

    harness.reset()
    settings = get_settings()
    fake = FakeClient(primary_always(fail=err(429, "RESOURCE_EXHAUSTED")))
    vl._CLIENTS.clear()
    vl._CLIENTS[(settings.google_cloud_project, settings.google_cloud_location)] = fake
    per_call = []
    for _ in range(calls):
        before = len(fake.models.calls)
        t0 = time.perf_counter()
        await VertexLLMProvider().generate_json(system="s", user="u")
        tried = fake.models.calls[before:]
        per_call.append({"primary_attempted": PRIMARY in tried,
                         "answered_by": tried[-1], "latency_sec": round(time.perf_counter() - t0, 3)})
    return {"calls": calls, "fail_max": settings.model_circuit_fail_max,
            "reset_seconds": settings.model_circuit_reset_seconds,
            "primary_attempts": sum(c["primary_attempted"] for c in per_call), "per_call": per_call}


async def main(trials: int) -> None:
    rows = []
    for name, behaviour in SCENARIOS.items():
        for i in range(trials):
            rows.append(await trial(name, behaviour))
        print(f"{name}: done", flush=True)
    probe = await circuit_probe()
    sustained = await sustained_probe()

    out = harness.RESULTS / "fault_injection"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "trials.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = []
    for name in SCENARIOS:
        rs = [r for r in rows if r["scenario"] == name]
        lat = [r["latency_sec"] for r in rs]
        outcomes = {o: sum(r["outcome"] == o for r in rs) for o in dict.fromkeys(r["outcome"] for r in rs)}
        summary.append({
            "scenario": name, "trials": len(rs), "outcomes": outcomes,
            "usable_output_rate": sum(r["outcome"] in ("primary model", "fallback model") for r in rs) / len(rs),
            "mean_attempts": statistics.mean(r["attempts"] for r in rs),
            "latency_median_sec": statistics.median(lat), "latency_max_sec": max(lat),
            "models_tried": rs[0]["models_tried"], "second_call_model": rs[0]["second_call_model"],
            "degraded_flagged": sum(r["degraded_flagged"] for r in rs),
        })
    harness.save_json(out / "summary.json", {"label": "mock-based fault injection",
                                              "primary_model": PRIMARY, "scenarios": summary,
                                              "circuit_breaker_probe": probe,
                                              "sustained_429_probe": sustained})
    print(json.dumps(summary, indent=1))
    print(json.dumps(probe, indent=1))
    print(json.dumps(sustained, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20)
    args = ap.parse_args()
    harness.configure_env("faults")
    import os

    os.environ["LLM_PROVIDER"] = "vertex"
    os.environ["GEMINI_MODEL_GENERATE"] = PRIMARY
    os.environ["VERTEX_MODEL"] = ""
    harness.install()
    asyncio.run(main(args.trials))
