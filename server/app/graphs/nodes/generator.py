import asyncio
from typing import Any

from app.graphs.agents import AGENT_REGISTRY
from app.graphs.state import JobGraphState


async def generator(state: JobGraphState) -> dict[str, Any]:
    """Dispatches parallel execution to specialized creator agents based on requested_types."""
    transcript = state.get("transcript_text") or ""
    brief = state.get("brief") or {}
    user_memory = state.get("user_memory") or {}
    requested = state.get("requested_types") or list(AGENT_REGISTRY.keys())

    # Filter agents to run
    agents_to_run = [
        agent_cls()
        for type_name, agent_cls in AGENT_REGISTRY.items()
        if type_name in requested or (type_name == "ig_caption" and "instagram" in requested)
    ]

    if not agents_to_run:
        agents_to_run = [agent_cls() for agent_cls in AGENT_REGISTRY.values()]

    # Run specialized agents concurrently in parallel
    tasks = [
        agent.generate(
            transcript_text=transcript,
            brief=brief,
            user_memory=user_memory,
        )
        for agent in agents_to_run
    ]

    pieces = await asyncio.gather(*tasks)
    return {"generated": list(pieces), "retry_count": int(state.get("retry_count") or 0)}
