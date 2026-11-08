"""Tools the writer agents may call (only when AGENT_TOOLS_ENABLED=true).

Every tool returns real data or says plainly that it found none. A tool never invents
a result: on an empty search or an error it tells the model not to cite outside facts."""

import structlog
from duckduckgo_search import DDGS
from langchain_core.tools import tool

from app.core.config import get_settings

logger = structlog.get_logger("agent_tools")


def _no_results(what: str, query: str) -> str:
    return (
        f"No {what} found for '{query}'. Do not cite outside facts; "
        "write from the transcript and the brief only."
    )


@tool
def search_web(query: str) -> str:
    """Search the web for one real-world fact or statistic to cite in a post.
    Provide a specific search query. Returns titles and snippets, or a note that nothing was found.
    """
    logger.info("tool_invoked", tool="search_web", query=query)
    try:
        results = list(DDGS(timeout=get_settings().tool_timeout_seconds).text(query, max_results=3))
    except Exception as exc:
        logger.error("tool_error", tool="search_web", error=str(exc))
        return _no_results("web results", query)
    if not results:
        return _no_results("web results", query)
    lines = [f"- {r.get('title', '')} ({r.get('href', '')}): {r.get('body', '')}" for r in results]
    return "Web search results (outside sources, not from the session):\n" + "\n".join(lines)


@tool
def fetch_industry_news(topic: str) -> str:
    """Fetch up to three recent news items on a topic for a newsletter.
    Returns headlines with dates and links, or a note that nothing was found.
    """
    logger.info("tool_invoked", tool="fetch_industry_news", topic=topic)
    try:
        results = list(DDGS(timeout=get_settings().tool_timeout_seconds).news(topic, max_results=3))
    except Exception as exc:
        logger.error("tool_error", tool="fetch_industry_news", error=str(exc))
        return _no_results("news", topic)
    if not results:
        return _no_results("news", topic)
    lines = [
        f"- {r.get('title', '')} ({r.get('date', '')}, {r.get('url', '')}): {r.get('body', '')}"
        for r in results
    ]
    return "Recent news (outside sources, not from the session):\n" + "\n".join(lines)
