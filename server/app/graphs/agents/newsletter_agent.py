from app.graphs.agents.base import BaseCreatorAgent


class NewsletterAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="newsletter", skill_filename="newsletter_skill.md")
