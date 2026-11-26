from app.graphs.agents.base import BaseCreatorAgent


class LinkedInAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="linkedin", skill_filename="linkedin_skill.md")
