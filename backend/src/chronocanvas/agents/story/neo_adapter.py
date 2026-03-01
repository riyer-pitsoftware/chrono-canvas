"""Bridge neo_modules to chrono-canvas LLM router.

Provides an async ``llm_fn`` callable that routes through the chrono-canvas
LLM infrastructure (Gemini via EXTRACTION task type) instead of Ollama.
"""

from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router


async def llm_fn_for_neo(prompt: str) -> str:
    """LLM function compatible with neo_modules.extraction.extract_characters.

    Routes through the chrono-canvas LLM router using EXTRACTION task type
    (defaults to Gemini).
    """
    router = get_llm_router()
    response = await router.generate(
        prompt=prompt,
        task_type=TaskType.EXTRACTION,
        temperature=0.3,
        max_tokens=4000,
        json_mode=True,
    )
    return response.content
