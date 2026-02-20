from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TaskType(StrEnum):
    EXTRACTION = "extraction"
    RESEARCH = "research"
    PROMPT_GENERATION = "prompt_generation"
    VALIDATION = "validation"
    ORCHESTRATION = "orchestration"
    GENERAL = "general"


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    metadata: dict[str, Any] = {}
    system_prompt: str | None = None
    user_prompt: str | None = None
    duration_ms: float = 0.0


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...
