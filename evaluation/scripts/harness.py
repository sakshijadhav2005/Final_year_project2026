"""Instrumentation for evaluation runs of the real EventAI backend.

Nothing here changes application behaviour: functions are wrapped only to record
wall-clock timings (time.perf_counter) and the token usage that the Google SDKs
return with every response. Stage labels propagate through contextvars, which
asyncio copies into the tasks LangGraph creates for parallel nodes.

Import order matters: call `configure_env()` before anything imports `app`.
"""

from __future__ import annotations

import contextvars
import json
import os
import sys
import time
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
SERVER = EVAL.parent / "server"
RESULTS = EVAL / "results"

STAGE: contextvars.ContextVar[str] = contextvars.ContextVar("stage", default="other")
CALLS: list[dict] = []
STAGES: list[dict] = []


def configure_env(db_name: str) -> None:
    """Isolated SQLite DB + media folder per worker; never the developer's data.
    Provider/model settings still come from the project .env (recorded per run)."""
    work = EVAL / "work"
    work.mkdir(exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(work / f'{db_name}.db').as_posix()}"
    os.environ["MEDIA_ROOT"] = str(work / f"media_{db_name}")
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["USE_CELERY"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["SENTRY_DSN"] = ""
    os.environ["DEBUG"] = "false"  # keeps SQL debug logging out of the run logs
    sys.path.insert(0, str(SERVER))
    os.chdir(SERVER)


def reset() -> None:
    """Clear the logs and the provider's process-wide state (circuit breakers, dead
    models), so every run starts from the configured model; any fallback inside a run is
    visible in CALLS."""
    CALLS.clear()
    STAGES.clear()
    import app.providers.vertex_llm as vl
    from app.services.resilience import llm_circuit, reset_model_circuits, stt_circuit

    for name in ("_WORKING_MODEL", "_WORKING_FAST_MODEL"):  # versions before the fix
        if hasattr(vl, name):
            setattr(vl, name, None)
    vl._DEAD_MODELS.clear()
    reset_model_circuits()
    llm_circuit.reset()
    stt_circuit.reset()


def _usage(resp) -> dict:
    u = getattr(resp, "usage_metadata", None)
    cands = getattr(resp, "candidates", None) or []
    finish = getattr(cands[0], "finish_reason", None) if cands else None
    return {
        "finish_reason": str(finish) if finish is not None else None,
        "empty_text": resp is not None and not (getattr(resp, "text", None) or "").strip(),
        "prompt_tokens": getattr(u, "prompt_token_count", None),
        "output_tokens": getattr(u, "candidates_token_count", None),
        "thoughts_tokens": getattr(u, "thoughts_token_count", None),
        "total_tokens": getattr(u, "total_token_count", None),
    }


def install() -> None:
    import logging

    for name in ("aiosqlite", "httpx", "httpcore", "google", "urllib3", "sqlalchemy"):
        logging.getLogger(name).setLevel(logging.WARNING)

    from google.genai import models as gmodels

    orig_gen = gmodels.AsyncModels.generate_content
    orig_emb = gmodels.AsyncModels.embed_content

    async def generate_content(self, *, model, contents, config=None):
        t0 = time.perf_counter()
        resp = err = None
        try:
            resp = await orig_gen(self, model=model, contents=contents, config=config)
            return resp
        except BaseException as exc:
            err = f"{type(exc).__name__}: {str(exc)[:200]}"
            raise
        finally:
            CALLS.append(
                {"kind": "llm", "stage": STAGE.get(), "model": model, "t0": t0,
                 "sec": time.perf_counter() - t0, "error": err, **_usage(resp)}
            )

    async def embed_content(self, *, model, contents, config=None):
        t0 = time.perf_counter()
        resp = err = None
        try:
            resp = await orig_emb(self, model=model, contents=contents, config=config)
            return resp
        except BaseException as exc:
            err = f"{type(exc).__name__}: {str(exc)[:200]}"
            raise
        finally:
            meta = getattr(resp, "metadata", None)
            CALLS.append(
                {"kind": "embed", "stage": STAGE.get(), "model": model, "t0": t0,
                 "sec": time.perf_counter() - t0, "error": err,
                 "inputs": len(contents) if isinstance(contents, list) else 1,
                 "billable_chars": getattr(meta, "billable_character_count", None)}
            )

    gmodels.AsyncModels.generate_content = generate_content
    gmodels.AsyncModels.embed_content = embed_content

    # Speech-to-text uses the google.generativeai SDK synchronously in an executor thread.
    import google.generativeai as legacy

    orig_stt = legacy.GenerativeModel.generate_content
    orig_upload = legacy.upload_file

    def stt_generate(self, *args, **kwargs):
        t0 = time.perf_counter()
        resp = err = None
        try:
            resp = orig_stt(self, *args, **kwargs)
            return resp
        except BaseException as exc:
            err = f"{type(exc).__name__}: {str(exc)[:200]}"
            raise
        finally:
            CALLS.append(
                {"kind": "stt", "stage": "stt", "model": getattr(self, "model_name", "?"),
                 "t0": t0, "sec": time.perf_counter() - t0, "error": err, **_usage(resp)}
            )

    def upload_file(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return orig_upload(*args, **kwargs)
        finally:
            CALLS.append({"kind": "stt_upload", "stage": "stt", "model": None, "t0": t0,
                          "sec": time.perf_counter() - t0, "error": None})

    legacy.GenerativeModel.generate_content = stt_generate
    legacy.upload_file = upload_file

    # Graph nodes: patched in the pipeline module before the graph is compiled.
    import app.graphs.pipeline as pipeline

    def timed_node(name, fn):
        async def node(state):
            label = name
            if name == "generator" and int(state.get("retry_count") or 0) > 0:
                label = "generator_retry"
            token = STAGE.set(label)
            t0 = time.perf_counter()
            try:
                return await fn(state)
            finally:
                STAGES.append({"stage": label, "t0": t0, "t1": time.perf_counter(),
                               "agent": state.get("agent_type")})
                STAGE.reset(token)

        node.__name__ = fn.__name__
        return node

    for attr, label in (
        ("quality_check", "quality_gate"),
        ("parallel_analysis", "analysis"),
        ("content_planner", "planner"),
        ("rag_retrieve", "rag_retrieve"),
        ("generator", "generator"),
        ("guardrail", "guardrail"),
        ("translation", "translation"),
        ("persist_fail", "persist_fail"),
    ):
        setattr(pipeline, attr, timed_node(label, getattr(pipeline, attr)))
    pipeline._compiled = None

    # Job-runner steps outside the graph.
    import app.services.job_runner as jr

    def timed_async(name, fn):
        async def wrapper(*args, **kwargs):
            token = STAGE.set(name)
            t0 = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                STAGES.append({"stage": name, "t0": t0, "t1": time.perf_counter(), "agent": None})
                STAGE.reset(token)

        return wrapper

    def timed_sync(name, fn):
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                STAGES.append({"stage": name, "t0": t0, "t1": time.perf_counter(), "agent": None})

        return wrapper

    jr.transcribe_file = timed_async("stt", jr.transcribe_file)
    jr.index_transcript_chunks = timed_async("rag_index", jr.index_transcript_chunks)
    jr.load_rag_pool = timed_async("rag_pool", jr.load_rag_pool)
    jr.inspect_media = timed_sync("media_check", jr.inspect_media)


def config_snapshot() -> dict:
    from app.core.config import get_settings

    s = get_settings()
    return {
        "llm_provider": s.llm_provider,
        "stt_provider": s.stt_provider,
        "gemini_model_generate": s.gemini_model_generate,
        "gemini_model_analyze": s.gemini_model_analyze,
        "gemini_model_fast": s.gemini_model_fast,
        "vertex_model": s.vertex_model,
        "google_cloud_location": s.google_cloud_location,
        "rag_enabled": s.rag_enabled,
        "rag_token_threshold": s.rag_token_threshold,
        "rag_top_k": s.rag_top_k,
        "rag_embedding_model": s.rag_embedding_model,
        "rag_embedding_dims": s.rag_embedding_dims,
        "rag_embedding_location": s.rag_embedding_location,
        "vertex_stt_model": s.vertex_stt_model or s.gemini_model_analyze,
        "stt_chunk_seconds": s.stt_chunk_seconds,
        "stt_concurrency": s.stt_concurrency,
        "agent_tools_enabled": s.agent_tools_enabled,
        "llm_timeout_seconds": s.llm_timeout_seconds,
    }


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
