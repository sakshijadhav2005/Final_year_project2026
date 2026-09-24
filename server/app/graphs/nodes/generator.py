import asyncio
from typing import Any

from app.graphs.agents import AGENT_REGISTRY


async def generator(state: dict[str, Any]) -> dict[str, Any]:
    """Runs a single specialized creator agent dynamically spawned by the Send API."""
    transcript = state.get("transcript_text") or ""
    brief = state.get("brief") or {}
    user_memory = state.get("user_memory") or {}
    
    # Extract the dynamic agent_type from the Send payload
    agent_type = state.get("agent_type")
    
    # Ensure the agent exists in the registry, fallback to a dummy/default if needed
    agent_cls = AGENT_REGISTRY.get(agent_type)
    if not agent_cls:
        # If unknown, just skip or return empty
        return {"generated": []}
        
    agent = agent_cls()

    # Generate the content piece
    piece = await agent.generate(
        transcript_text=transcript,
        brief=brief,
        user_memory=user_memory,
    )

    # Return as a list so the Annoted[list, operator.add] reducer can safely aggregate it 
    # with the outputs of other parallel agents!
    return {"generated": [piece], "retry_count": int(state.get("retry_count") or 0)}
