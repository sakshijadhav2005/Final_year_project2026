from typing import Any

from app.core.config import get_settings
from app.graphs.state import JobGraphState
from app.services.rag import rank_chunks


def _brief_query(state: JobGraphState) -> str:
    """What the writers are about to write: the brief's angle and key messages,
    plus the extracted topics and highlights."""
    brief = state.get("brief") or {}
    parts: list[str] = []
    if isinstance(brief, dict):
        parts.append(str(brief.get("angle") or ""))
        messages = brief.get("key_messages") or []
        parts.extend(str(m) for m in (messages if isinstance(messages, list) else [messages]))
    for key in ("topics", "highlights"):
        value = (state.get(key) or {}).get(key) if isinstance(state.get(key), dict) else None
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
    return "\n".join(p for p in parts if p.strip())[:4000]


async def rag_retrieve(state: JobGraphState) -> dict[str, Any]:
    """Selective RAG: pick the transcript chunks most relevant to the brief for the
    writing agents. A no-op when the job_runner built no candidate pool."""
    pool = state.get("rag_pool") or []
    if not pool:
        return {"rag_chunks": []}
    query = _brief_query(state)
    model, chunks = await rank_chunks(pool, query, get_settings().rag_top_k)
    return {
        "rag_chunks": chunks,
        "rag_meta": {"model": model, "query": query, "pool_size": len(pool)},
    }
