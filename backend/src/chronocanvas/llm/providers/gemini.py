import asyncio
import logging
from collections.abc import Awaitable, Callable

from google import genai
from google.genai import types

from chronocanvas.config import settings
from chronocanvas.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Per-call timeout for Gemini API requests (seconds)
_REQUEST_TIMEOUT = 120

GEMINI_REQUEST_TIMEOUT = _REQUEST_TIMEOUT  # public alias for direct-call sites


async def gemini_generate_with_timeout(client: genai.Client, **kwargs) -> object:
    """Wrap client.aio.models.generate_content with a timeout.

    Use this for any direct Gemini call outside the LLM router (vision nodes,
    TTS, coherence, scene editor, etc.).  All kwargs are forwarded to
    ``client.aio.models.generate_content()``.
    """
    return await asyncio.wait_for(
        client.aio.models.generate_content(**kwargs),
        timeout=_REQUEST_TIMEOUT,
    )


GEMINI_PRICING = {
    "gemini-2.5-flash": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
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

        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            ),
            timeout=_REQUEST_TIMEOUT,
        )

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        content = response.text or ""
        if not content.strip():
            logger.warning(
                "Gemini returned empty response (model=%s, finish_reason=%s, input_tokens=%d)",
                self.model,
                getattr(response.candidates[0], "finish_reason", "unknown") if response.candidates else "no_candidates",
                input_tokens,
            )

        return LLMResponse(
            content=content,
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

        async def _stream():
            nonlocal full_text, input_tokens, output_tokens
            stream = await client.aio.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )
            async for chunk in stream:
                if chunk.text:
                    full_text += chunk.text
                    if on_token:
                        await on_token(chunk.text)
                if chunk.usage_metadata:
                    input_tokens = chunk.usage_metadata.prompt_token_count or input_tokens
                    output_tokens = chunk.usage_metadata.candidates_token_count or output_tokens

        await asyncio.wait_for(_stream(), timeout=_REQUEST_TIMEOUT)

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

    async def generate_with_search(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate with Gemini Google Search grounding tool."""
        client = self._get_client()

        config_kwargs: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "tools": [types.Tool(google_search=types.GoogleSearch())],
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_kwargs)

        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            ),
            timeout=_REQUEST_TIMEOUT,
        )

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        content = response.text or ""

        # Extract grounding metadata (citations) from the response
        grounding_citations = []
        candidate = response.candidates[0] if response.candidates else None
        if candidate and hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
            gm = candidate.grounding_metadata
            for chunk in getattr(gm, "grounding_chunks", []) or []:
                web = getattr(chunk, "web", None)
                if web:
                    grounding_citations.append({
                        "title": getattr(web, "title", "") or "",
                        "url": getattr(web, "uri", "") or "",
                        "publisher": None,
                        "quote_snippet": None,
                        "claim_supported": None,
                        "confidence": 1.0,
                    })

        return LLMResponse(
            content=content,
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            metadata={"grounding_citations": grounding_citations},
        )

    async def is_available(self) -> bool:
        return bool(settings.google_api_key)
