import logging
import time

from chronocanvas.agents.state import AgentState
from chronocanvas.content_moderation import check_input

logger = logging.getLogger(__name__)


async def orchestrator_node(state: AgentState) -> AgentState:
    logger.info(f"Orchestrator: processing request {state.get('request_id', 'unknown')}")

    input_text = state.get("input_text", "")
    is_safe, reason = check_input(input_text)

    trace_entry: dict = {
        "agent": "orchestrator",
        "action": "start",
        "timestamp": time.time(),
        "input_text": input_text,
        "moderation": {"passed": is_safe, "reason": reason if not is_safe else None},
    }

    trace = list(state.get("agent_trace", []))
    trace.append(trace_entry)

    if not is_safe:
        logger.warning(
            "Orchestrator: input blocked by content moderation [request_id=%s] — %s",
            state.get("request_id", "unknown"),
            reason,
        )
        return {
            "current_agent": "orchestrator",
            "agent_trace": trace,
            "retry_count": state.get("retry_count", 0),
            "should_regenerate": False,
            "error": f"Content policy violation: {reason}",
        }

    return {
        "current_agent": "orchestrator",
        "agent_trace": trace,
        "retry_count": state.get("retry_count", 0),
        "should_regenerate": False,
        "error": None,
    }
