import logging
import time

from historylens.config import settings
from historylens.llm.base import LLMProvider, LLMResponse, TaskType
from historylens.llm.cost_tracker import CostTracker
from historylens.llm.providers.claude import ClaudeProvider
from historylens.llm.providers.ollama import OllamaProvider
from historylens.llm.providers.openai import OpenAIProvider
from historylens.llm.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Default routing: which provider to prefer for each task type
DEFAULT_ROUTING: dict[TaskType, str] = {
    TaskType.EXTRACTION: "ollama",
    TaskType.RESEARCH: "claude",
    TaskType.PROMPT_GENERATION: "claude",
    TaskType.VALIDATION: "claude",
    TaskType.ORCHESTRATION: "ollama",
    TaskType.GENERAL: "ollama",
}


class LLMRouter:
    def __init__(self):
        self.providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(),
            "claude": ClaudeProvider(),
            "openai": OpenAIProvider(),
        }
        self.rate_limiter = RateLimiter(
            max_rpm=settings.rate_limit_rpm,
            max_concurrent=settings.llm_max_concurrent,
        )
        self.cost_tracker = CostTracker()

    def get_provider(self, task_type: TaskType = TaskType.GENERAL) -> LLMProvider:
        preferred = DEFAULT_ROUTING.get(task_type, settings.default_llm_provider)
        if preferred in self.providers:
            return self.providers[preferred]
        return self.providers[settings.default_llm_provider]

    async def generate(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        provider_override: str | None = None,
    ) -> LLMResponse:
        if provider_override and provider_override in self.providers:
            provider = self.providers[provider_override]
        else:
            provider = self.get_provider(task_type)

        # Fallback chain: preferred -> ollama -> any available
        if not await provider.is_available():
            for name, p in self.providers.items():
                if name != provider.name and await p.is_available():
                    logger.warning(f"Falling back from {provider.name} to {name}")
                    provider = p
                    break

        start = time.perf_counter()
        async with self.rate_limiter:
            response = await provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.system_prompt = system_prompt
        response.user_prompt = prompt
        response.duration_ms = elapsed_ms

        self.cost_tracker.record(
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost=response.cost,
            task_type=task_type,
        )

        return response

    async def check_availability(self) -> dict[str, bool]:
        result = {}
        for name, provider in self.providers.items():
            result[name] = await provider.is_available()
        return result


# Singleton
llm_router = LLMRouter()
