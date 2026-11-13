"""Turn the writers' Markdown into the plain text social platforms display."""

from __future__ import annotations

import re

HASHTAG = re.compile(r"(?<![\w&/])#(\w+)")
MENTION = re.compile(r"(?<![\w.])@([A-Za-z0-9_.]+)")


def plain_text(markdown: str) -> str:
    """Social feeds show text as typed, so drop the Markdown markers the writers produce."""
    text = (markdown or "").replace("\r\n", "\n")
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)  # bold
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", text)  # links
    text = re.sub(r"^(\s*)[*-]\s+", r"\1• ", text, flags=re.MULTILINE)  # bullets
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
