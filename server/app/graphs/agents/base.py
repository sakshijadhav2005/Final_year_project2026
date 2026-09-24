from pathlib import Path
from typing import Any

from app.providers.factory import get_llm_provider
from app.services.resilience import llm_circuit, with_backoff

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


class BaseCreatorAgent:
    """Base class for specialized content creator agents reading skill.md instructions."""

    def __init__(self, agent_name: str, skill_filename: str):
        self.agent_name = agent_name
        self.skill_filename = skill_filename
        self._skill_content = self._load_skill()

    def _load_skill(self) -> str:
        skill_path = SKILLS_DIR / self.skill_filename
        if skill_path.exists():
            try:
                return skill_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return f"You are a specialized {self.agent_name} copywriter. Generate authentic, high-quality copy."

    def _build_system_prompt(self, user_memory: dict | None = None) -> str:
        memory = user_memory or {}
        author_info = (
            f"Author Full Name: {memory.get('full_name', 'Event Speaker/Author')}\n"
            f"Organization: {memory.get('organization', 'Tech Community')}\n"
            f"Job Title: {memory.get('job_title', 'Speaker')}\n"
            f"Bio: {memory.get('bio', '')}\n"
            f"LinkedIn Handle: {memory.get('linkedin_handle', '')}\n"
            f"Instagram Handle: {memory.get('instagram_handle', '')}\n"
            f"Website: {memory.get('website_url', '')}\n"
            f"Brand Tone: {memory.get('brand_tone', 'authoritative_inspiring')}\n"
            f"Custom Sign-off: {memory.get('custom_signoff', '')}\n"
        )
        return (
            f"{self._skill_content}\n\n"
            f"### INJECTED AUTHOR BRAND & CENTRALIZED MEMORY:\n{author_info}\n\n"
            "Return JSON only with keys:\n"
            '{"type": "<type_name>", "title": "<engaging_title>", "body": "<markdown_formatted_body>", "structured": {}}\n'
            "Strictly follow all instructions and negative constraints in the skill guideline above."
        )

    async def generate(
        self,
        transcript_text: str,
        brief: dict | None = None,
        user_memory: dict | None = None,
        temperature: float = 0.35,
    ) -> dict[str, Any]:
        llm = get_llm_provider()
        system_prompt = self._build_system_prompt(user_memory)
        brief_str = str(brief) if brief else "N/A"
        user_prompt = (
            "Here is the context you must use to generate the post:\n\n"
            f"<EDITORIAL_BRIEF>\n{brief_str}\n</EDITORIAL_BRIEF>\n\n"
            f"<TRANSCRIPT>\n{transcript_text[:12000]}\n</TRANSCRIPT>\n\n"
            f"Now, please generate the final {self.agent_name} post matching your system instructions."
        )

        async def _call() -> dict[str, Any]:
            result = await llm.generate_json(
                system=system_prompt,
                user=user_prompt,
                temperature=temperature,
            )
            return result

        try:
            res = await with_backoff(_call, circuit=llm_circuit)
            if "type" not in res:
                res["type"] = self.agent_name
            if "body" not in res and "text" in res:
                res["body"] = res["text"]
            return res
        except Exception:
            return {
                "type": self.agent_name,
                "title": f"Key Takeaways ({self.agent_name.title()})",
                "body": f"Highlights from the session:\n\n{transcript_text[:500]}...",
                "structured": {},
            }
