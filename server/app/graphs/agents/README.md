# Specialized Creator Agents (Member 3)

This directory houses the 6 autonomous LLM Creator Agents. Each agent is decoupled, reads its persona prompt from `server/app/graphs/skills/<type>_skill.md`, and dynamically injects the user's Centralized Brand Memory (`UserProfile`).

## Agents Directory Map:
- `base.py`: Abstract foundation class (`BaseCreatorAgent`) providing skill markdown file loading, memory injection, resilience circuit breaker, and JSON extraction.
- `linkedin_agent.py`: Generates viral hooks, actionable insights, and Pune tech community hashtags.
- `instagram_agent.py`: Generates visual carousel copy and aesthetic reel caption.
- `newsletter_agent.py`: Writes executive subscriber updates with TL;DR and key takeaways.
- `blog_agent.py`: Crafts deep-dive markdown technical articles.
- `summary_agent.py`: Condenses sessions into high-impact executive summaries.
- `flyer_agent.py`: Produces punchy visual headlines and bullet points for event flyers.
- `__init__.py`: Registry (`AGENT_REGISTRY`) mapping content types to agent classes.
