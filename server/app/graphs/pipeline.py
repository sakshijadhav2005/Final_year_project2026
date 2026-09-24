from langgraph.graph import END, START, StateGraph

from app.graphs.nodes import (
    content_planner,
    generator,
    guardrail,
    parallel_analysis,
    persist_fail,
    quality_check,
    translation,
)
from app.graphs.state import JobGraphState


def rag_should_run(transcript_tokens: int, use_org_memory: bool, threshold: int) -> bool:
    return use_org_memory or transcript_tokens > threshold


def _after_quality(state: JobGraphState) -> str:
    return "needs_reupload" if state.get("route") == "needs_reupload" else "parallel_analysis"


def _after_guardrail(state: JobGraphState) -> str:
    route = state.get("route")
    if route == "retry_generate":
        return "generator"
    if route == "needs_review":
        return "persist_fail"
    return "translation"


from langgraph.types import Send

def dynamic_router(state: JobGraphState):
    """Dynamically spawns parallel nodes based on user's requested_types."""
    requested = state.get("requested_types") or ["linkedin", "blog", "newsletter", "summary", "flyer", "instagram"]
    
    # We use LangGraph's Send API to fan-out dynamically.
    # Each Send object creates a new instance of the 'dynamic_generator' node.
    sends = []
    for req in requested:
        # We pass the agent_type down, the node will use the rest from the overall state.
        # Note: In Python, passing the state dict by reference is cheap.
        sends.append(Send("dynamic_generator", {"agent_type": req, **state}))
    return sends


def build_graph():
    """Builds and compiles the production LangGraph StateGraph pipeline."""
    graph = StateGraph(JobGraphState)

    # Register single-responsibility nodes
    graph.add_node("quality_check", quality_check)
    graph.add_node("parallel_analysis", parallel_analysis)
    graph.add_node("content_planner", content_planner)
    
    # We replace the static generator with our dynamic generator node
    graph.add_node("dynamic_generator", generator)
    
    graph.add_node("guardrail_node", guardrail)
    graph.add_node("translation", translation)
    graph.add_node("persist_fail", persist_fail)

    # Stage 1: Audio/Video validation gate
    graph.add_edge(START, "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        _after_quality,
        {"needs_reupload": END, "parallel_analysis": "parallel_analysis"},
    )

    # Stage 2: Parallel extraction fan-out (topics, highlights, speakers, sentiment)
    graph.add_edge("parallel_analysis", "content_planner")

    # Stage 3: Master brief synthesis -> Stage 4: Dynamic Send Router
    graph.add_conditional_edges("content_planner", dynamic_router, ["dynamic_generator"])

    # Stage 4 outputs automatically gather and proceed to Guardrails
    graph.add_edge("dynamic_generator", "guardrail_node")

    # Stage 5: Guardrails verification gate & Stage 6: Multi-language localization
    graph.add_conditional_edges(
        "guardrail_node",
        _after_guardrail,
        {"generator": "content_planner", "persist_fail": "persist_fail", "translation": "translation"},
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
