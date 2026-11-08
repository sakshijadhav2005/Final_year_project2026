from app.graphs.agents.base import BaseCreatorAgent
from app.graphs.tools import search_web


class BlogAgent(BaseCreatorAgent):
    tools = (search_web,)
    tool_hint = (
        "If one specific statistic in the transcript would clearly benefit from a citation, "
        "you may call `search_web` once. Otherwise answer directly without tools."
    )

    def __init__(self):
        super().__init__(agent_name="blog", skill_filename="blog_skill.md")
