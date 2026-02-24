from typing import Any

from chronocanvas.agents.state import AgentState, ExtractionState, PromptState, ResearchState

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

        extracted = request.extracted_data or {}
        if extracted:
            state["extraction"] = ExtractionState(
                **{k: v for k, v in extracted.items() if v is not None}
            )

        researched = request.research_data or {}
        if researched:
            state["research"] = ResearchState(
                **{k: v for k, v in researched.items() if v is not None}
            )

        if request.generated_prompt:
            state["prompt"] = PromptState(image_prompt=request.generated_prompt)

        predecessor = _PREDECESSOR_NODE.get(from_step)
        if predecessor:
            for entry in reversed(request.agent_trace or []):
                if entry.get("agent") == predecessor and entry.get("state_snapshot"):
                    snapshot = entry["state_snapshot"]
                    # Merge any namespaced sub-dicts from the snapshot
                    for key in ("extraction", "research", "prompt", "image",
                                "validation", "face", "compositing", "export"):
                        if key in snapshot and key not in state:
                            state[key] = snapshot[key]  # type: ignore[literal-required]
                    # Merge flat control fields
                    for key in ("current_agent", "input_text"):
                        if key in snapshot and key not in state:
                            state[key] = snapshot[key]  # type: ignore[literal-required]
                    break

        return state
