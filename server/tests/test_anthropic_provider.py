"""Claude (Anthropic API) provider: real SDK, fake HTTP transport (no network, no key)."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx2 as httpx  # the anthropic SDK 2.x ships its own httpx2
import pytest
from app.core.config import get_settings
from app.providers import anthropic_llm


def _reply(text: str) -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


@pytest.fixture
def claude(monkeypatch):
    """Point the real Anthropic SDK at a fake transport and record every request."""
    from anthropic import AsyncAnthropic

    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(s, "anthropic_model", "claude-sonnet-5-5")
    monkeypatch.setattr(s, "anthropic_fallback_model", "claude-haiku-5-5")
    monkeypatch.setattr(s, "anthropic_effort", "low")
    monkeypatch.setattr(anthropic_llm, "_DEAD_MODELS", set())

    state = {"requests": [], "handler": lambda body: httpx.Response(200, json=_reply('{"ok": true}'))}

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        auth = request.headers.get("x-api-key") or request.headers.get("authorization", "").removeprefix("Bearer ")
        state["requests"].append({"body": body, "key": auth})
        return state["handler"](body)

    client = AsyncAnthropic(
        api_key="sk-ant-test",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    monkeypatch.setattr(anthropic_llm, "get_client", lambda: client)
    return state


def test_request_shape_follows_current_claude_api(claude):
    out = asyncio.run(anthropic_llm.AnthropicLLMProvider().generate_json(system="sys", user="TASK=x", temperature=0.9))
    assert out == {"ok": True}
    body = claude["requests"][0]["body"]
    assert claude["requests"][0]["key"] == "sk-ant-test"
    assert body["model"] == "claude-sonnet-5-5"
    assert body["output_config"] == {"effort": "low"}
    assert "temperature" not in body  # rejected by current models
    assert body["messages"][-1]["role"] == "user"  # no assistant prefill
    assert "JSON" in body["system"]


def test_reply_in_code_fence_is_parsed(claude):
    claude["handler"] = lambda b: httpx.Response(200, json=_reply('```json\n{"title": "Hi"}\n```'))
    out = asyncio.run(anthropic_llm.AnthropicLLMProvider().generate_json(system="s", user="u"))
    assert out == {"title": "Hi"}


def test_unavailable_model_falls_back_once_and_is_remembered(claude):
    def handler(body):
        if body["model"] == "claude-sonnet-5-5":
            return httpx.Response(404, json={"type": "error", "error": {"type": "not_found_error", "message": "model"}})
        return httpx.Response(200, json=_reply('{"ok": 1}'))

    claude["handler"] = handler
    p = anthropic_llm.AnthropicLLMProvider()
    for _ in range(3):
        assert asyncio.run(p.generate_json(system="s", user="u")) == {"ok": 1}
    models = [r["body"]["model"] for r in claude["requests"]]
    assert models == ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-haiku-5-5", "claude-haiku-5-5"]


def test_effort_rejected_is_retried_without_it(claude):
    def handler(body):
        if "output_config" in body:
            return httpx.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "effort is not supported"}})
        return httpx.Response(200, json=_reply('{"ok": 2}'))

    claude["handler"] = handler
    assert asyncio.run(anthropic_llm.AnthropicLLMProvider().generate_json(system="s", user="u")) == {"ok": 2}


def test_bad_key_falls_back_to_offline_generator(claude):
    claude["handler"] = lambda b: httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
    out = asyncio.run(anthropic_llm.AnthropicLLMProvider().generate_json(system="s", user="TASK=summary\nhello"))
    assert isinstance(out, dict) and out  # the demo keeps working


def test_factory_selects_claude(monkeypatch):
    from app.providers.factory import get_llm_provider

    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    for name in ("anthropic", "claude", "Claude "):
        monkeypatch.setattr(s, "llm_provider", name)
        assert get_llm_provider().name == "anthropic"
    monkeypatch.setattr(s, "llm_provider", "gemini")
    monkeypatch.setattr(s, "gemini_api_key", "g")
    assert get_llm_provider().name == "gemini"
    monkeypatch.setattr(s, "anthropic_api_key", "")
    monkeypatch.setattr(s, "llm_provider", "anthropic")
    assert get_llm_provider().name == "gemini"  # no Claude key -> next available


def test_whole_pipeline_runs_on_claude(claude, monkeypatch):
    """Every pipeline step goes through Claude when LLM_PROVIDER=anthropic."""
    from app.graphs.pipeline import get_compiled_graph
    from app.providers.fake_llm import FakeLLMProvider

    monkeypatch.setattr(get_settings(), "llm_provider", "anthropic")
    fake = FakeLLMProvider()

    def handler(body):  # answer like Claude would, using the offline generator's content
        coro = fake.generate_json(system=body["system"], user=body["messages"][0]["content"])
        with ThreadPoolExecutor(1) as pool:  # handler runs inside the graph's event loop
            result = pool.submit(asyncio.run, coro).result()
        return httpx.Response(200, json=_reply(json.dumps(result)))

    claude["handler"] = handler
    state = {
        "job_id": "t", "user_id": "u", "avg_confidence": 0.99, "quality": {"ok": True},
        "transcript_text": "Speaker 1: Welcome to the EventAI meetup on multi-agent pipelines and guardrails.",
        "requested_types": ["summary", "blog", "linkedin"], "target_languages": ["en", "hi"],
        "use_org_memory": False, "user_memory": {}, "retry_count": 0, "rag_chunks": [],
    }
    final = asyncio.run(get_compiled_graph().ainvoke(state))
    assert len(final["generated"]) == 3
    assert len(final["translations"]) == 3
    assert len(claude["requests"]) >= 5  # analysis, 3 drafts, guardrail, translation
    by_task = {}
    for r in claude["requests"]:
        task = r["body"]["messages"][0]["content"].split("\n", 1)[0].removeprefix("TASK=")
        by_task.setdefault(task, set()).add(r["body"]["model"])
    # posts are written by the main model, the checking steps by the quick one
    assert by_task["blog"] == {"claude-sonnet-5-5"}
    assert by_task["guardrail_batch"] == {"claude-haiku-5-5"}
    assert by_task["translation_batch"] == {"claude-haiku-5-5"}


def test_copilot_chat_streams_from_claude(claude, monkeypatch):
    from app.services.chat_service import stream_chat_response

    monkeypatch.setattr(get_settings(), "llm_provider", "anthropic")
    events = (
        'event: message_start\ndata: {"type":"message_start","message":{"id":"m","type":"message","role":"assistant",'
        '"model":"claude-sonnet-5-5","content":[],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":1,"output_tokens":1}}}\n\n'
        'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
        'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello "}}\n\n'
        'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"there"}}\n\n'
        'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
        'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":2}}\n\n'
        'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    )
    claude["handler"] = lambda b: httpx.Response(200, text=events, headers={"content-type": "text/event-stream"})

    async def collect():
        msgs = [{"role": "assistant", "content": "Hi! Ask me anything."}, {"role": "user", "content": "Key quote?"}]
        return [e async for e in stream_chat_response(msgs, persona="organizer_copilot", transcript_text="talk")]

    out = asyncio.run(collect())
    chunks = [json.loads(e.removeprefix("data: "))["chunk"] for e in out]
    assert "".join(chunks) == "Hello there"
    body = claude["requests"][0]["body"]
    assert body["stream"] is True
    assert body["messages"][0]["role"] == "user"  # leading assistant greeting dropped
