from typing import Any
import json
import structlog
from app.graphs.agents.base import BaseCreatorAgent
from app.graphs.tools import get_trending_hashtags
from app.core.config import get_settings

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
    ) -> dict[str, Any]:
        """Overrides the standard generation to use a LangGraph ReAct agent with custom tools!"""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langgraph.prebuilt import create_react_agent
            from langchain_core.messages import SystemMessage, HumanMessage
            import re
            
            settings = get_settings()
            
            # 1. Initialize the LLM with native tool support
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                api_key=settings.gemini_api_key,
                temperature=temperature
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
                f"<TRANSCRIPT>\n{transcript_text[:12000]}\n</TRANSCRIPT>\n\n"
                f"Now, please generate the final {self.agent_name} post matching your system instructions. "
                "CRITICAL: Before writing the hashtags at the bottom of the post, you MUST use your "
                "`get_trending_hashtags` tool to fetch the absolute best viral hashtags for the topic!"
            )
            
            # 5. Execute the Agent loop! It will automatically call tools if needed.
            logger.info("linkedin_agent_started_with_tools")
            response = await agent_executor.ainvoke({
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
            })
            
            # 6. Extract the final response text
            final_text = response["messages"][-1].content
            
            # Ensure it is parsed as JSON as expected by the pipeline
            match = re.search(r"\{[\s\S]*\}", final_text)
            if match:
                return json.loads(match.group(0))
            
            return {"type": "linkedin", "title": "EventAI LinkedIn Post", "body": final_text, "structured": {}}
            
        except Exception as exc:
            logger.error("linkedin_agent_tool_error", error=str(exc))
            # Fallback to the standard base agent without tools
            return await super().generate(transcript_text, brief, user_memory, temperature)

