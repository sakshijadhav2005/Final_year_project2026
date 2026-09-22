from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.graphs.state import JobGraphState
from app.providers.factory import get_llm_provider
from app.providers.gemini_llm import analysis_system, build_user_prompt, generation_system
from app.services.guardrails import grounding_check, moderate_text, should_use_rag
from app.services.resilience import llm_circuit, with_backoff


def rag_should_run(transcript_tokens: int, use_org_memory: bool, threshold: int) -> bool:
    return use_org_memory or transcript_tokens > threshold


async def quality_check(state: JobGraphState) -> dict[str, Any]:
    quality = state.get("quality") or {}
    if quality.get("ok") is False:
        return {"route": "needs_reupload"}
    avg = state.get("avg_confidence")
    if isinstance(avg, (int, float)) and avg < 0.35:
        return {"route": "needs_reupload"}
    return {"route": "continue"}


async def _agent(task: str, state: JobGraphState, temperature: float = 0.2) -> dict[str, Any]:
    llm = get_llm_provider()

    async def _call() -> dict[str, Any]:
        return await llm.generate_json(
            system=analysis_system(),
            user=build_user_prompt(task, state.get("transcript_text", "")),
            temperature=temperature,
        )

    return await with_backoff(_call, circuit=llm_circuit)


async def topic_extraction(state: JobGraphState) -> dict[str, Any]:
    return {"topics": await _agent("topic_extraction", state)}


async def highlight_detection(state: JobGraphState) -> dict[str, Any]:
    return {"highlights": await _agent("highlight_detection", state)}


async def speaker_analysis(state: JobGraphState) -> dict[str, Any]:
    return {"speakers": await _agent("speaker_analysis", state)}


async def sentiment_analysis(state: JobGraphState) -> dict[str, Any]:
    return {"sentiment": await _agent("sentiment_analysis", state)}


async def fan_out(state: JobGraphState) -> dict[str, Any]:
    return {"route": state.get("route") or "continue"}


async def content_planner(state: JobGraphState) -> dict[str, Any]:
    llm = get_llm_provider()
    extra = (
        f"Topics={state.get('topics')}\nHighlights={state.get('highlights')}\n"
        f"Speakers={state.get('speakers')}\nSentiment={state.get('sentiment')}\n"
        f"Requested types={state.get('requested_types')}"
    )

    async def _call() -> dict[str, Any]:
        return await llm.generate_json(
            system=analysis_system(),
            user=build_user_prompt("content_planner", state.get("transcript_text", ""), extra),
            temperature=0.2,
        )

    return {"brief": await with_backoff(_call, circuit=llm_circuit)}


async def rag_retrieve(state: JobGraphState) -> dict[str, Any]:
    existing = state.get("rag_chunks") or []
    if existing:
        return {"rag_chunks": existing}
    settings = get_settings()
    transcript = state.get("transcript_text") or ""
    if not should_use_rag(transcript, bool(state.get("use_org_memory")), settings.rag_token_threshold):
        return {"rag_chunks": []}
    words = transcript.split()
    chunk = " ".join(words[:400])
    return {"rag_chunks": [{"text": chunk, "source": "transcript_head"}]}


async def generator(state: JobGraphState) -> dict[str, Any]:
    llm = get_llm_provider()
    extra = (
        f"Brief={state.get('brief')}\nTypes={state.get('requested_types')}\n"
        f"RAG={state.get('rag_chunks')}"
    )

    async def _call() -> dict[str, Any]:
        return await llm.generate_json(
            system=generation_system(),
            user=build_user_prompt("generator", state.get("transcript_text", ""), extra),
            temperature=0.35,
        )

    result = await with_backoff(_call, circuit=llm_circuit)
    pieces = result.get("pieces") or []
    requested = state.get("requested_types") or []
    if requested:
        filtered = [p for p in pieces if p.get("type") in requested]
        if filtered:
            pieces = filtered
    return {"generated": pieces, "retry_count": int(state.get("retry_count") or 0)}


async def guardrail(state: JobGraphState) -> dict[str, Any]:
    transcript = state.get("transcript_text") or ""
    issues: list[str] = []
    generated = state.get("generated") or []
    if not generated:
        issues.append("No content generated")
    for piece in generated:
        body = str(piece.get("body") or "")
        mod = moderate_text(body)
        ground = grounding_check(body, transcript)
        piece["moderation"] = mod
        piece["grounding"] = ground
        if not mod["pass"]:
            issues.append(f"moderation:{piece.get('type')}")
        if not ground["pass"]:
            issues.append(f"grounding:{piece.get('type')}")
    retry_count = int(state.get("retry_count") or 0)
    if issues and retry_count < 1:
        return {
            "route": "retry_generate",
            "retry_count": retry_count + 1,
            "guardrail": {"pass": False, "issues": issues},
        }
    if issues:
        return {"route": "needs_review", "guardrail": {"pass": False, "issues": issues}, "generated": generated}
    return {"route": "continue", "guardrail": {"pass": True, "issues": []}, "generated": generated}


async def translation(state: JobGraphState) -> dict[str, Any]:
    languages = [lang for lang in (state.get("target_languages") or ["en"]) if lang and lang != "en"]
    if not languages:
        return {"translations": []}
    llm = get_llm_provider()
    translations: list[dict[str, Any]] = []
    for lang in languages:
        for piece in state.get("generated") or []:

            async def _call(p=piece, language=lang) -> dict[str, Any]:
                return await llm.generate_json(
                    system=generation_system(),
                    user=build_user_prompt(
                        "translation",
                        state.get("transcript_text", ""),
                        f"Translate this {p.get('type')} into {language}. JSON with keys title, body.\n"
                        f"Title={p.get('title')}\nBody={p.get('body')}",
                    ),
                    temperature=0.2,
                )

            result = await with_backoff(_call, circuit=llm_circuit)
            translations.append(
                {
                    "type": piece.get("type"),
                    "language": lang,
                    "title": result.get("title") or piece.get("title"),
                    "body": result.get("text") or result.get("body") or piece.get("body"),
                    "parent_type": piece.get("type"),
                }
            )
    return {"translations": translations}


def _after_quality(state: JobGraphState) -> str:
    return "needs_reupload" if state.get("route") == "needs_reupload" else "fan_out"


def _after_guardrail(state: JobGraphState) -> str:
    route = state.get("route")
    if route == "retry_generate":
        return "generator"
    if route == "needs_review":
        return "persist_fail"
    return "translation"


async def persist_fail(state: JobGraphState) -> dict[str, Any]:
    return {"route": "needs_review"}


def build_graph():
    graph = StateGraph(JobGraphState)
    graph.add_node("quality_check", quality_check)
    graph.add_node("fan_out", fan_out)
    graph.add_node("topic_extraction", topic_extraction)
    graph.add_node("highlight_detection", highlight_detection)
    graph.add_node("speaker_analysis", speaker_analysis)
    graph.add_node("sentiment_analysis", sentiment_analysis)
    graph.add_node("content_planner", content_planner)
    graph.add_node("rag_retrieve", rag_retrieve)
    graph.add_node("generator", generator)
    graph.add_node("guardrail_node", guardrail)
    graph.add_node("translation", translation)
    graph.add_node("persist_fail", persist_fail)

    graph.add_edge(START, "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        _after_quality,
        {"needs_reupload": END, "fan_out": "fan_out"},
    )
    graph.add_edge("fan_out", "topic_extraction")
    graph.add_edge("fan_out", "highlight_detection")
    graph.add_edge("fan_out", "speaker_analysis")
    graph.add_edge("fan_out", "sentiment_analysis")
    graph.add_edge("topic_extraction", "content_planner")
    graph.add_edge("highlight_detection", "content_planner")
    graph.add_edge("speaker_analysis", "content_planner")
    graph.add_edge("sentiment_analysis", "content_planner")
    graph.add_edge("content_planner", "rag_retrieve")
    graph.add_edge("rag_retrieve", "generator")
    graph.add_edge("generator", "guardrail_node")
    graph.add_conditional_edges(
        "guardrail_node",
        _after_guardrail,
        {"generator": "generator", "persist_fail": "persist_fail", "translation": "translation"},
    )
    graph.add_edge("persist_fail", END)
    graph.add_edge("translation", END)
    return graph.compile()


_compiled = None


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
