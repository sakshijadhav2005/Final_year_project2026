# Specialized Creator Agents (Member 3)

This directory houses the 6 autonomous LLM Creator Agents. Each agent is decoupled, reads its persona prompt from `server/app/graphs/skills/<type>_skill.md`, and dynamically injects the user's Centralized Brand Memory (`UserProfile`).

All writers share one implementation in `base.py`. A subclass only names its skill file and,
optionally, the tools it may call (`tools`, `tool_hint`). With `AGENT_TOOLS_ENABLED=true`, a
writer that has tools first asks the model (one small JSON call through the configured provider)
whether one lookup would help and with what input; the code runs at most that one tool with a
timeout and passes the result to the writer as labelled outside sources. Any failure skips the
lookup. Native function calling is not used: Gemini 3 requires thought signatures that the pinned
LangChain integration does not return. Only `blog` (`search_web`) and
`newsletter` (`fetch_industry_news`) have tools; both return real search results or say that
nothing was found (see `../tools.py`).

## Agents Directory Map:
- `base.py`: `BaseCreatorAgent`: skill loading, memory injection, the optional tool loop, the plain call with circuit breaker, and JSON extraction.
- `linkedin_agent.py`: Generates viral hooks, actionable insights, and Pune tech community hashtags.
- `instagram_agent.py`: Generates visual carousel copy and aesthetic reel caption.
- `newsletter_agent.py`: Writes executive subscriber updates with TL;DR and key takeaways.
- `blog_agent.py`: Crafts deep-dive markdown technical articles.
- `summary_agent.py`: Condenses sessions into high-impact executive summaries.
- `flyer_agent.py`: Produces punchy visual headlines and bullet points for event flyers.
- `__init__.py`: Registry (`AGENT_REGISTRY`) mapping content types to agent classes.
