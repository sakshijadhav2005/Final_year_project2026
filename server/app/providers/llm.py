from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate_json(self, *, system: str, user: str, temperature: float = 0.3) -> dict[str, Any]:
        raise NotImplementedError
