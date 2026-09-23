from app.graphs.agents.base import BaseCreatorAgent


class SummaryAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="summary", skill_filename="summary_skill.md")
