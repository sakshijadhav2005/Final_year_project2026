from app.graphs.agents.base import BaseCreatorAgent
from app.graphs.agents.blog_agent import BlogAgent
from app.graphs.agents.flyer_agent import FlyerAgent
from app.graphs.agents.instagram_agent import InstagramAgent
from app.graphs.agents.linkedin_agent import LinkedInAgent
from app.graphs.agents.newsletter_agent import NewsletterAgent
from app.graphs.agents.summary_agent import SummaryAgent

AGENT_REGISTRY: dict[str, type[BaseCreatorAgent]] = {
    "summary": SummaryAgent,
    "blog": BlogAgent,
    "linkedin": LinkedInAgent,
    "newsletter": NewsletterAgent,
    "ig_caption": InstagramAgent,
    "flyer": FlyerAgent,
}

__all__ = [
    "AGENT_REGISTRY",
    "BaseCreatorAgent",
    "BlogAgent",
    "FlyerAgent",
    "InstagramAgent",
    "LinkedInAgent",
    "NewsletterAgent",
    "SummaryAgent",
]
