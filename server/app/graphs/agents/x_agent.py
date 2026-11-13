from typing import Any

from app.graphs.agents.base import BaseCreatorAgent
from app.services.publishers.text import plain_text
from app.services.publishers.x import MAX_TEXT, weighted_length


def fit_x_limit(body: str, limit: int = MAX_TEXT) -> str:
    """Plain text within X's limit; overlong drafts are cut at a word boundary with "…"."""
    text = plain_text(body)
    if weighted_length(text) <= limit:
        return text
    words = text.split(" ")
    while words and weighted_length(" ".join(words) + "…") > limit:
        words.pop()
    return (" ".join(words).rstrip(" ,;:-") + "…") if words else text[: limit - 1] + "…"


class XAgent(BaseCreatorAgent):
    """One post for X (Twitter), within 280 characters."""

    def __init__(self):
        super().__init__(agent_name="x_post", skill_filename="x_skill.md")

    async def generate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        piece = await super().generate(*args, **kwargs)
        if isinstance(piece.get("body"), str):
            piece["body"] = fit_x_limit(piece["body"])
        return piece
