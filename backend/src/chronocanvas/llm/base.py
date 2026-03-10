from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
    metadata: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None
    user_prompt: str | None = None
    duration_ms: float = 0.0
    requested_provider: str | None = None
    fallback: bool = False


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
    ) -> LLMResponse: ...

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Stream tokens via on_token callback; falls back to non-streaming by default."""
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    async def generate_with_search(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate with grounded search (Google Search). Falls back to plain generate."""
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    @abstractmethod
    async def is_available(self) -> bool: ...
