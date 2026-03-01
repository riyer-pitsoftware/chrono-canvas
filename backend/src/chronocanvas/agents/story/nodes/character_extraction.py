import logging
import time

from chronocanvas.agents.story.neo_adapter import llm_fn_for_neo
from chronocanvas.agents.story.state import StoryState

logger = logging.getLogger(__name__)


async def character_extraction_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    input_text = state.get("input_text", "")
    logger.info("Character extraction: processing [request_id=%s]", request_id)

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    try:
        from neo_modules.extraction import extract_characters

        start = time.perf_counter()
        result = await extract_characters(input_text, llm_fn=llm_fn_for_neo)
        elapsed_ms = (time.perf_counter() - start) * 1000

        characters = result.get("characters", [])
        logger.info(
            "Extracted %d characters [request_id=%s]", len(characters), request_id
        )

        trace.append({
            "agent": "character_extraction",
            "timestamp": time.time(),
            "characters_found": len(characters),
            "character_names": [c.get("name", "?") for c in characters],
        })

        llm_calls.append({
            "agent": "character_extraction",
            "timestamp": time.time(),
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "duration_ms": elapsed_ms,
            "requested_provider": "gemini",
            "fallback": False,
        })

        return {
            "current_agent": "character_extraction",
            "characters": characters,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        logger.exception("Character extraction failed [request_id=%s]", request_id)
        trace.append({
            "agent": "character_extraction",
            "timestamp": time.time(),
            "error": str(e),
        })
        return {
            "current_agent": "character_extraction",
            "characters": [],
            "agent_trace": trace,
            "llm_calls": llm_calls,
            "error": f"Character extraction failed: {e}",
        }
