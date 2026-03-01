from collections.abc import Awaitable, Callable

from google import genai
from google.genai import types

from chronocanvas.config import settings
from chronocanvas.llm.base import LLMProvider, LLMResponse

GEMINI_PRICING = {
    "gemini-2.0-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    "gemini-2.0-flash-lite": {"input": 0.0 / 1_000_000, "output": 0.0 / 1_000_000},
    "gemini-1.5-flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
    "gemini-1.5-pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
}


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        self.model = settings.gemini_model
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.google_api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()

        config_kwargs: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_kwargs)

        response = await client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        return LLMResponse(
            content=response.text or "",
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        client = self._get_client()

        config_kwargs: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_kwargs)

        full_text = ""
        input_tokens = 0
        output_tokens = 0

        async for chunk in client.aio.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                full_text += chunk.text
                if on_token:
                    await on_token(chunk.text)
            if chunk.usage_metadata:
                input_tokens = chunk.usage_metadata.prompt_token_count or input_tokens
                output_tokens = chunk.usage_metadata.candidates_token_count or output_tokens

        pricing = GEMINI_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        return LLMResponse(
            content=full_text,
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

    async def is_available(self) -> bool:
        return bool(settings.google_api_key)
