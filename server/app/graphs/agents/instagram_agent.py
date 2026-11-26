from app.graphs.agents.base import BaseCreatorAgent


class InstagramAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="instagram", skill_filename="instagram_skill.md")
