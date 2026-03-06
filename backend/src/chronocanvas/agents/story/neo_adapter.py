"""Bridge neo_modules to chrono-canvas LLM router.

Provides an async ``llm_fn`` callable that routes through the chrono-canvas
LLM infrastructure (Gemini via EXTRACTION task type) instead of Ollama.
"""

from chronocanvas.llm.base import LLMResponse, TaskType
from chronocanvas.llm.router import get_llm_router


class NeoLLMBridge:
    """Wraps the LLM router to capture response metadata for cost tracking.

    Usage::

        bridge = NeoLLMBridge()
        result = await extract_characters(text, llm_fn=bridge)
        # bridge.last_response has token counts, cost, etc.
    """

    def __init__(self, runtime_config=None) -> None:
        self.last_response: LLMResponse | None = None
        self.last_prompt: str | None = None
        self._runtime_config = runtime_config

    async def __call__(self, prompt: str) -> str:
        self.last_prompt = prompt
        router = get_llm_router()
        self.last_response = await router.generate(
            prompt=prompt,
            task_type=TaskType.EXTRACTION,
            temperature=0.3,
            max_tokens=4000,
            json_mode=True,
            runtime_config=self._runtime_config,
        )
        return self.last_response.content


# Backward-compatible simple function (no metadata capture)
async def llm_fn_for_neo(prompt: str) -> str:
    """LLM function compatible with neo_modules.extraction.extract_characters."""
    bridge = NeoLLMBridge()
    return await bridge(prompt)
