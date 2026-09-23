from app.graphs.agents.base import BaseCreatorAgent


class FlyerAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="flyer", skill_filename="flyer_skill.md")
