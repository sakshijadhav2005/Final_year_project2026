"""The pipeline must make as few sequential LLM calls as possible."""

import asyncio
import sys
import types

from app.graphs.pipeline import get_compiled_graph
from app.providers import fake_llm

TRANSCRIPT = (
    "Speaker 1: Welcome to the EventAI meetup on intelligent content operations. "
    "Today we discuss multi-agent pipelines, guardrails and human review."
)
TYPES = ["summary", "blog", "linkedin", "newsletter", "ig_caption", "flyer"]


def _run(monkeypatch, *, flag_first_check: bool = False, languages=("en", "hi", "es")):
    calls: list[str] = []
    orig = fake_llm.FakeLLMProvider.generate_json

    async def counting(self, *, system, user, temperature=0.3, **_):
        task = next((ln.split("=", 1)[1] for ln in user.splitlines() if ln.startswith("TASK=")), "other")
        calls.append(task)
        if flag_first_check and task == "guardrail_batch" and calls.count("guardrail_batch") == 1:
            return {"results": {"blog": {"grounding_pass": False, "moderation_pass": True, "issues": ["x"]}}}
        return await orig(self, system=system, user=user, temperature=temperature)

    monkeypatch.setattr(fake_llm.FakeLLMProvider, "generate_json", counting)
    state = {
        "job_id": "t",
        "user_id": "u",
        "transcript_text": TRANSCRIPT,
        "avg_confidence": 0.99,
        "quality": {"ok": True},
        "requested_types": TYPES,
        "target_languages": list(languages),
        "use_org_memory": False,
        "user_memory": {},
        "retry_count": 0,
        "rag_chunks": [],
    }
    final = asyncio.run(get_compiled_graph().ainvoke(state))
    return final, calls


def test_guardrail_is_one_batched_call(monkeypatch):
    final, calls = _run(monkeypatch)
    assert calls.count("guardrail_batch") == 1
    assert len(final["generated"]) == 6
    assert all("grounding" in p and "moderation" in p for p in final["generated"])


def test_translation_is_one_call_per_language(monkeypatch):
    final, calls = _run(monkeypatch, languages=("en", "hi", "es"))
    assert calls.count("translation_batch") == 2
    assert len(final["translations"]) == 12
    assert {t["language"] for t in final["translations"]} == {"hi", "es"}


def test_retry_regenerates_only_failed_drafts(monkeypatch):
    final, calls = _run(monkeypatch, flag_first_check=True, languages=("en",))
    # 6 drafts first time + only the 1 failed draft again, planner not re-run
    generator_calls = [c for c in calls if c in {"summary", "blog", "linkedin", "newsletter", "instagram", "flyer"}]
    assert len(generator_calls) == 7
    assert calls.count("content_planner") <= 1
    assert calls.count("guardrail_batch") == 2
    assert len(final["generated"]) == 6


def test_gemini_skips_dead_models_and_remembers_working_one(monkeypatch):
    """A wrong model name costs one failed request once, not on every call."""
    from app.core.config import get_settings
    from app.providers import gemini_llm

    requests: list[str] = []

    class FakeModel:
        def __init__(self, name, system_instruction=None):
            self.name = name

        async def generate_content_async(self, *_a, **_k):
            requests.append(self.name)
            if self.name == "gemini-wrong-name":
                raise RuntimeError("404 models/gemini-wrong-name is not found")
            return types.SimpleNamespace(text='{"ok": true}')

    fake_genai = types.SimpleNamespace(configure=lambda **_: None, GenerativeModel=FakeModel)
    google_pkg = types.ModuleType("google")
    google_pkg.generativeai = fake_genai
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model_generate", "gemini-wrong-name")
    monkeypatch.setattr(gemini_llm, "_DEAD_MODELS", set())
    monkeypatch.setattr(gemini_llm, "_CONFIGURED_KEY", None)

    provider = gemini_llm.GeminiLLMProvider()
    for _ in range(3):
        assert asyncio.run(provider.generate_json(system="s", user="u")) == {"ok": True}

    # wrong model tried exactly once (no retry on a permanent 404), then never again
    assert requests.count("gemini-wrong-name") == 1
    assert requests[1:] == ["gemini-3.6-flash"] * 3


def test_portkey_key_alone_does_not_reroute_gemini(monkeypatch):
    """LLM_PROVIDER=gemini must use Gemini directly even if a Portkey key exists."""
    from app.core.config import get_settings
    from app.providers.factory import get_llm_provider, get_stt_provider

    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "gemini")
    monkeypatch.setattr(s, "gemini_api_key", "g-key")
    monkeypatch.setattr(s, "portkey_api_key", "p-key")
    monkeypatch.setattr(s, "videodb_api_key", "v-key")
    monkeypatch.setattr(s, "stt_provider", "auto")
    assert get_llm_provider().name == "gemini"
    assert get_stt_provider().name == "gemini-stt"  # auto prefers the faster engine
    monkeypatch.setattr(s, "stt_provider", "videodb")
    assert get_stt_provider().name == "videodb"
    monkeypatch.setattr(s, "llm_provider", "portkey")
    assert get_llm_provider().name == "portkey"


def test_portkey_skips_dead_route(monkeypatch):
    from app.core.config import get_settings
    from app.providers import portkey_llm

    s = get_settings()
    for k, v in {"portkey_api_key": "p", "openai_api_key": "", "groq_api_key": "", "gemini_api_key": "g"}.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(portkey_llm, "_DEAD_STRATEGIES", set())

    hits: list[str] = []

    class FakeCompletions:
        async def create(self, **_):
            hits.append("portkey")
            raise RuntimeError("401 Unauthorized: invalid api key")

    class FakeOpenAI:
        def __init__(self, **_):
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeOpenAI))

    async def fake_gemini(self, *, system, user, temperature=0.3):
        hits.append("gemini")
        return {"ok": True}

    from app.providers import gemini_llm

    monkeypatch.setattr(gemini_llm.GeminiLLMProvider, "generate_json", fake_gemini)
    p = portkey_llm.PortkeyLLMProvider()
    for _ in range(3):
        assert asyncio.run(p.generate_json(system="s", user="u")) == {"ok": True}
    # the broken Portkey route is tried once (no retry on 401), then Gemini is used directly
    assert hits == ["portkey", "gemini", "gemini", "gemini"]


def test_checking_steps_use_the_fast_model_and_posts_do_not(monkeypatch):
    """Safety check + translation go to GEMINI_MODEL_FAST; drafts keep the main model."""
    from app.core.config import get_settings
    from app.providers import gemini_llm

    used: list[tuple[str, str]] = []

    class FakeModel:
        def __init__(self, name, system_instruction=None):
            self.name = name

        async def generate_content_async(self, prompt, **_k):
            task = next((ln.split("=", 1)[1] for ln in prompt.splitlines() if ln.startswith("TASK=")), "?")
            used.append((task, self.name))
            return types.SimpleNamespace(text='{"ok": true}')

    fake_genai = types.SimpleNamespace(configure=lambda **_: None, GenerativeModel=FakeModel)
    google_pkg = types.ModuleType("google")
    google_pkg.generativeai = fake_genai
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "k")
    monkeypatch.setattr(s, "gemini_model_generate", "gemini-3.6-flash")
    monkeypatch.setattr(s, "gemini_model_fast", "gemini-3.1-flash-lite")
    for name, value in {"_DEAD_MODELS": set(), "_CONFIGURED_KEY": None}.items():
        monkeypatch.setattr(gemini_llm, name, value)

    p = gemini_llm.GeminiLLMProvider()
    asyncio.run(p.generate_json(system="s", user="TASK=blog\nx"))
    asyncio.run(p.generate_json(system="s", user="TASK=guardrail_batch\nx", fast=True))
    asyncio.run(p.generate_json(system="s", user="TASK=linkedin\nx"))
    assert used == [
        ("blog", "gemini-3.6-flash"),
        ("guardrail_batch", "gemini-3.1-flash-lite"),
        ("linkedin", "gemini-3.6-flash"),
    ]
