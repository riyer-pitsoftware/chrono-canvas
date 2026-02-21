import openai

from chronocanvas.config import settings
from chronocanvas.llm.base import LLMProvider, LLMResponse

OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.0 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
}


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        self.model = settings.openai_model
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        pricing = OPENAI_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        return LLMResponse(
            content=response.choices[0].message.content or "",
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

    async def is_available(self) -> bool:
        return bool(settings.openai_api_key)
