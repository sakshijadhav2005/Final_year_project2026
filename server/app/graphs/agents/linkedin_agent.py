import asyncio
import json
from typing import Any

import structlog

from app.core.config import get_settings
from app.graphs.agents.base import BaseCreatorAgent, _retrieved_block
from app.services.rag import AGENT_TRANSCRIPT_CHARS
from app.graphs.tools import get_trending_hashtags

logger = structlog.get_logger("linkedin_agent")


class LinkedInAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="linkedin", skill_filename="linkedin_skill.md")

    async def generate(
        self,
        transcript_text: str,
        brief: dict | None = None,
        user_memory: dict | None = None,
        temperature: float = 0.35,
        context_chunks: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Overrides the standard generation to use a LangGraph ReAct agent with custom tools!"""
        try:
            import re

            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langgraph.prebuilt import create_react_agent
            
            settings = get_settings()
            if not settings.gemini_api_key or not settings.agent_tools_enabled:
                # Offline mode or tools switched off: one plain generation call (fastest).
                return await super().generate(transcript_text, brief, user_memory, temperature, context_chunks)
            
            # 1. Initialize the LLM with native tool support
            model_name = settings.gemini_model_generate or "gemini-3.6-flash"
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                api_key=settings.gemini_api_key,
                temperature=temperature,
                timeout=settings.llm_timeout_seconds,
                max_retries=1,
            )
            
            # 2. Bind our tools (The Hashtag Generator)
            tools = [get_trending_hashtags]
            
            # 3. Create the ReAct agent execution graph
            agent_executor = create_react_agent(llm, tools)
            
            # 4. Build Prompts
            system_prompt = self._build_system_prompt(user_memory)
            brief_str = str(brief) if brief else "N/A"
            user_prompt = (
                "Here is the context you must use to generate the post:\n\n"
                f"<EDITORIAL_BRIEF>\n{brief_str}\n</EDITORIAL_BRIEF>\n\n"
                f"<TRANSCRIPT>\n{transcript_text[:AGENT_TRANSCRIPT_CHARS]}\n</TRANSCRIPT>\n\n"
                f"{_retrieved_block(context_chunks)}"
                f"Now, please generate the final {self.agent_name} post matching your system instructions. "
                "CRITICAL: Before writing the hashtags at the bottom of the post, you MUST use your "
                "`get_trending_hashtags` tool to fetch the absolute best viral hashtags for the topic!"
            )
            
            # 5. Execute the Agent loop! It will automatically call tools if needed.
            logger.info("linkedin_agent_started_with_tools")
            response = await asyncio.wait_for(agent_executor.ainvoke({
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
            }), timeout=settings.agent_timeout_seconds)
            
            # 6. Extract the final response text
            content = response["messages"][-1].content
            # Newer Gemini chat models may return a list of content parts.
            final_text = (
                "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
                if isinstance(content, list)
                else str(content)
            )
            
            # Ensure it is parsed as JSON as expected by the pipeline
            match = re.search(r"\{[\s\S]*\}", final_text)
            if match:
                parsed = json.loads(match.group(0))
                parsed["type"] = self.agent_name
                return parsed
            
            return {"type": "linkedin", "title": "EventAI LinkedIn Post", "body": final_text, "structured": {}}
            
        except Exception as exc:
            logger.error("linkedin_agent_tool_error", error=str(exc))
            # Fallback to the standard base agent without tools
            return await super().generate(transcript_text, brief, user_memory, temperature, context_chunks)

