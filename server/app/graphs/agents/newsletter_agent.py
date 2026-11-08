from app.graphs.agents.base import BaseCreatorAgent
from app.graphs.tools import fetch_industry_news


class NewsletterAgent(BaseCreatorAgent):
    tools = (fetch_industry_news,)
    tool_hint = (
        "If one current news item on the session's main topic would help readers, you may call "
        "`fetch_industry_news` once and mention it as outside news, never as said in the session. "
        "Otherwise answer directly without tools."
    )

    def __init__(self):
        super().__init__(agent_name="newsletter", skill_filename="newsletter_skill.md")
