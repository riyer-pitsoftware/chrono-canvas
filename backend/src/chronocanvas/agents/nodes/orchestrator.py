import logging
import time

from chronocanvas.agents.state import AgentState

logger = logging.getLogger(__name__)


async def orchestrator_node(state: AgentState) -> AgentState:
    logger.info(f"Orchestrator: processing request {state.get('request_id', 'unknown')}")

    trace_entry = {
        "agent": "orchestrator",
        "action": "start",
        "timestamp": time.time(),
        "input_text": state.get("input_text", ""),
    }

    trace = state.get("agent_trace", [])
    trace.append(trace_entry)

    return {
        **state,
        "current_agent": "orchestrator",
        "agent_trace": trace,
        "retry_count": state.get("retry_count", 0),
        "should_regenerate": False,
        "error": None,
    }
