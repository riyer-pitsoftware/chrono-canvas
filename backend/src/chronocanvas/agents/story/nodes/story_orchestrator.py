import logging
import time

from chronocanvas.agents.story.state import StoryState
from chronocanvas.content_moderation import check_input

logger = logging.getLogger(__name__)


async def story_orchestrator_node(state: StoryState) -> StoryState:
    logger.info("Story orchestrator: processing request %s", state.get("request_id", "unknown"))

    input_text = state.get("input_text", "")
    is_safe, reason = check_input(input_text)

    trace_entry: dict = {
        "agent": "story_orchestrator",
        "action": "start",
        "timestamp": time.time(),
        "input_length": len(input_text),
        "moderation": {"passed": is_safe, "reason": reason if not is_safe else None},
    }

    trace = list(state.get("agent_trace", []))
    trace.append(trace_entry)

    if not is_safe:
        logger.warning(
            "Story orchestrator: input blocked [request_id=%s] — %s",
            state.get("request_id", "unknown"),
            reason,
        )
        return {
            "current_agent": "story_orchestrator",
            "agent_trace": trace,
            "error": f"Content policy violation: {reason}",
        }

    return {
        "current_agent": "story_orchestrator",
        "agent_trace": trace,
        "error": None,
    }
