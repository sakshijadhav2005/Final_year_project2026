from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate_json(
        self, *, system: str, user: str, temperature: float = 0.3, fast: bool = False
    ) -> dict[str, Any]:
        """fast=True: a short checking task (safety check, translation) that can use a
        lighter, quicker model than the one that writes the posts."""
        raise NotImplementedError
