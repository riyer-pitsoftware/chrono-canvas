from typing import Any

from chronocanvas.agents.state import AgentState

# Maps each retry step to the node that must have run just before it,
# used as `as_node` in aupdate_state to set LangGraph's `next` pointer.
_PREDECESSOR_NODE: dict[str, str] = {
    "extraction": "orchestrator",
    "research": "extraction",
    "prompt_generation": "research",
    "image_generation": "prompt_generation",
    "validation": "image_generation",
    "facial_compositing": "validation",
    "export": "facial_compositing",
}


class RetryCoordinator:
    """Handles checkpoint inspection and state reconstruction for pipeline retries."""

    def predecessor_for(self, from_step: str) -> str:
        return _PREDECESSOR_NODE[from_step]

    def rebuild_state_from_db(self, request: Any, from_step: str) -> AgentState:
        """Reconstruct AgentState from DB fields when the LangGraph checkpoint is gone.

        Used after a worker restart where the in-memory MemorySaver has been cleared.
        Rebuilds from denormalized DB columns first, then enriches from the predecessor
        node's state_snapshot stored inside agent_trace.
        """
        state: AgentState = {
            "request_id": str(request.id),
            "input_text": request.input_text,
            "agent_trace": list(request.agent_trace or []),
            "llm_calls": list(request.llm_calls or []),
            "retry_count": 0,
            "should_regenerate": False,
            "error": None,
        }

        for k, v in (request.extracted_data or {}).items():
            if v is not None:
                state[k] = v  # type: ignore[literal-required]
        for k, v in (request.research_data or {}).items():
            if v is not None:
                state[k] = v  # type: ignore[literal-required]
        if request.generated_prompt:
            state["image_prompt"] = request.generated_prompt  # type: ignore[typeddict-unknown-key]

        predecessor = _PREDECESSOR_NODE.get(from_step)
        if predecessor:
            for entry in reversed(request.agent_trace or []):
                if entry.get("agent") == predecessor and entry.get("state_snapshot"):
                    for k, v in entry["state_snapshot"].items():
                        if k not in state:
                            state[k] = v  # type: ignore[literal-required]
                    break

        return state
