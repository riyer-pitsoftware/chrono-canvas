import anthropic

from chronocanvas.config import settings
from chronocanvas.llm.base import LLMProvider, LLMResponse

CLAUDE_PRICING = {
    "claude-sonnet-4-5-20250929": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "claude-haiku-4-5-20251001": {"input": 0.80 / 1_000_000, "output": 4.0 / 1_000_000},
}


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self):
        self.model = settings.claude_model
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if json_mode and system_prompt:
            kwargs["system"] = system_prompt + "\n\nRespond with valid JSON only."

        response = await self.client.messages.create(**kwargs)

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        pricing = CLAUDE_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        return LLMResponse(
            content=response.content[0].text,
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

    async def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)
