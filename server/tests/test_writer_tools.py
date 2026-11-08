"""Writer tools return real data or say they found none, and a failing tool loop
falls back to one plain generation call."""

import asyncio
from types import SimpleNamespace

from app.graphs import tools
from app.graphs.agents import AGENT_REGISTRY
from app.graphs.agents.base import BaseCreatorAgent


class _BrokenDDGS:
    def __init__(self, *args, **kwargs):
        pass

    def text(self, *args, **kwargs):
        raise RuntimeError("network down")

    news = text


class _EmptyDDGS(_BrokenDDGS):
    def text(self, *args, **kwargs):
        return []

    news = text


def test_tools_never_invent_results(monkeypatch) -> None:
    for ddgs in (_BrokenDDGS, _EmptyDDGS):
        monkeypatch.setattr(tools, "DDGS", ddgs)
        for tool, arg in ((tools.search_web, "query"), (tools.fetch_industry_news, "topic")):
            out = tool.invoke({arg: "ai agents"})
            assert out.startswith("No ")
            assert "Do not cite outside facts" in out


def test_tools_label_results_as_outside_sources(monkeypatch) -> None:
    class _DDGS(_BrokenDDGS):
        def text(self, *args, **kwargs):
            return [{"title": "T", "href": "https://x.test", "body": "B"}]

        def news(self, *args, **kwargs):
            return [{"title": "N", "date": "2026-11-01", "url": "https://n.test", "body": "B"}]

    monkeypatch.setattr(tools, "DDGS", _DDGS)
    assert "https://x.test" in tools.search_web.invoke({"query": "q"})
    assert "not from the session" in tools.fetch_industry_news.invoke({"topic": "t"})


def test_only_blog_and_newsletter_have_tools() -> None:
    with_tools = {name for name, cls in AGENT_REGISTRY.items() if cls.tools}
    assert with_tools == {"blog", "newsletter"}


def _plain_llm(seen: dict):
    class _LLM:
        async def generate_json(self, *, system, user, temperature=0.3, fast=False):
            seen["plain_calls"] = seen.get("plain_calls", 0) + 1
            return {"title": "t", "body": "b"}

    return _LLM()


def test_failing_tool_step_falls_back_to_plain_call(monkeypatch) -> None:
    seen: dict = {}
    settings = SimpleNamespace(agent_tools_enabled=True)
    monkeypatch.setattr("app.graphs.agents.base.get_settings", lambda: settings)
    monkeypatch.setattr("app.graphs.agents.base.get_llm_provider", lambda: _plain_llm(seen))

    async def _boom(self, *args, **kwargs):
        seen["tool_step"] = True
        raise RuntimeError("tool step failed")

    monkeypatch.setattr(BaseCreatorAgent, "_tool_step", _boom)
    out = asyncio.run(AGENT_REGISTRY["blog"]().generate("transcript"))
    assert seen == {"tool_step": True, "plain_calls": 1}
    assert out["type"] == "blog"


def test_writer_without_tools_skips_tool_step(monkeypatch) -> None:
    seen: dict = {}
    settings = SimpleNamespace(agent_tools_enabled=True)
    monkeypatch.setattr("app.graphs.agents.base.get_settings", lambda: settings)
    monkeypatch.setattr("app.graphs.agents.base.get_llm_provider", lambda: _plain_llm(seen))

    async def _never(self, *args, **kwargs):
        raise AssertionError("tool step must not run for a writer without tools")

    monkeypatch.setattr(BaseCreatorAgent, "_tool_step", _never)
    out = asyncio.run(AGENT_REGISTRY["linkedin"]().generate("transcript"))
    assert seen == {"plain_calls": 1}
    assert out["type"] == "linkedin"


def _deciding_llm(decision: dict, prompts: list[dict]):
    class _LLM:
        async def generate_json(self, *, system, user, temperature=0.3, fast=False):
            prompts.append({"system": system, "user": user, "fast": fast})
            if len(prompts) == 1:
                return decision
            return {"title": "t", "body": "b"}

    return _LLM()


def _tools_on(monkeypatch, decision: dict, prompts: list[dict]) -> None:
    settings = SimpleNamespace(agent_tools_enabled=True, tool_timeout_seconds=1.0)
    monkeypatch.setattr("app.graphs.agents.base.get_settings", lambda: settings)
    monkeypatch.setattr("app.graphs.agents.base.get_llm_provider", lambda: _deciding_llm(decision, prompts))


def test_model_picks_tool_and_writer_sees_labelled_result(monkeypatch) -> None:
    prompts: list[dict] = []
    _tools_on(monkeypatch, {"tool": "search_web", "input": "AI assistant adoption 2026"}, prompts)
    asked: list[str] = []

    class _DDGS(_BrokenDDGS):
        def text(self, query, **kwargs):
            asked.append(query)
            return [{"title": "Survey", "href": "https://s.test", "body": "62% use assistants"}]

    monkeypatch.setattr(tools, "DDGS", _DDGS)
    out = asyncio.run(AGENT_REGISTRY["blog"]().generate("62 percent use AI assistants"))
    assert asked == ["AI assistant adoption 2026"]
    assert len(prompts) == 2 and prompts[0]["fast"] is True
    assert "search_web" in prompts[0]["user"]
    writer = prompts[1]["user"]
    assert "<OUTSIDE_SOURCES>" in writer and "https://s.test" in writer
    assert "not from the session" in writer
    assert out["type"] == "blog"


def test_no_tool_or_unknown_tool_means_no_lookup(monkeypatch) -> None:
    for decision in ({"tool": None, "input": ""}, {"tool": "get_trending_hashtags", "input": "ai"}):
        prompts: list[dict] = []
        _tools_on(monkeypatch, decision, prompts)
        monkeypatch.setattr(tools, "DDGS", _BrokenDDGS)  # would raise if a search ran
        asyncio.run(AGENT_REGISTRY["newsletter"]().generate("transcript"))
        assert len(prompts) == 2
        assert "<OUTSIDE_SOURCES>" not in prompts[1]["user"]
