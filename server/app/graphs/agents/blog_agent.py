from app.graphs.agents.base import BaseCreatorAgent


class BlogAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="blog", skill_filename="blog_skill.md")
