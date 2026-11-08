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


def test_failing_tool_loop_falls_back_to_plain_call(monkeypatch) -> None:
    seen: dict = {}
    settings = SimpleNamespace(gemini_api_key="key", agent_tools_enabled=True)
    monkeypatch.setattr("app.graphs.agents.base.get_settings", lambda: settings)
    monkeypatch.setattr("app.graphs.agents.base.get_llm_provider", lambda: _plain_llm(seen))

    async def _boom(self, *args, **kwargs):
        seen["tool_loop"] = True
        raise RuntimeError("tool loop failed")

    monkeypatch.setattr(BaseCreatorAgent, "_generate_with_tools", _boom)
    out = asyncio.run(AGENT_REGISTRY["blog"]().generate("transcript"))
    assert seen == {"tool_loop": True, "plain_calls": 1}
    assert out["type"] == "blog"


def test_writer_without_tools_skips_tool_loop(monkeypatch) -> None:
    seen: dict = {}
    settings = SimpleNamespace(gemini_api_key="key", agent_tools_enabled=True)
    monkeypatch.setattr("app.graphs.agents.base.get_settings", lambda: settings)
    monkeypatch.setattr("app.graphs.agents.base.get_llm_provider", lambda: _plain_llm(seen))

    async def _never(self, *args, **kwargs):
        raise AssertionError("tool loop must not run for a writer without tools")

    monkeypatch.setattr(BaseCreatorAgent, "_generate_with_tools", _never)
    out = asyncio.run(AGENT_REGISTRY["linkedin"]().generate("transcript"))
    assert seen == {"plain_calls": 1}
    assert out["type"] == "linkedin"
