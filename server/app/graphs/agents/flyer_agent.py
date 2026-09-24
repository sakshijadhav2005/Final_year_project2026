import json
import structlog
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from app.core.config import get_settings
from app.graphs.agents.base import BaseCreatorAgent
from app.graphs.tools import generate_image_prompt, get_color_psychology

logger = structlog.get_logger("flyer_agent")

class FlyerAgent(BaseCreatorAgent):
    def __init__(self):
        super().__init__(agent_name="flyer", skill_filename="flyer_skill.md")

    async def generate(
        self,
        transcript_text: str,
        brief: dict | None = None,
        user_memory: dict | None = None,
        temperature: float = 0.35,
    ) -> dict[str, Any]:
        try:
            import re
            
            settings = get_settings()
            
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                api_key=settings.gemini_api_key,
                temperature=temperature
            )
            
            tools = [generate_image_prompt, get_color_psychology]
            
            system_prompt = self._build_system_prompt(user_memory)
            
            agent_executor = create_react_agent(llm, tools, state_modifier=system_prompt)
            
            brief_str = str(brief) if brief else "N/A"
            user_prompt = (
                "Here is the context you must use to generate the flyer:\n\n"
                f"<EDITORIAL_BRIEF>\n{brief_str}\n</EDITORIAL_BRIEF>\n\n"
                f"<TRANSCRIPT>\n{transcript_text[:12000]}\n</TRANSCRIPT>\n\n"
                f"Now, please generate the final {self.agent_name} matching your system instructions. "
                "IMPORTANT: You MUST return a pure JSON string. Do not use Markdown code blocks. Just start with { and end with }."
            )
            
            response = await agent_executor.ainvoke({
                "messages": [("user", user_prompt)]
            })
            
            last_message = response["messages"][-1].content
            
            json_str = last_message.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            
            res = json.loads(json_str)
            if "type" not in res:
                res["type"] = self.agent_name
            if "body" not in res and "text" in res:
                res["body"] = res["text"]
            return res
            
        except Exception as exc:
            logger.error("flyer_agent_tool_error", error=str(exc))
            return await super().generate(transcript_text, brief, user_memory, temperature)
