from typing import Any

from chronocanvas.db.models.request import RequestStatus

_STATUS_MAP: dict[str, RequestStatus] = {
    "orchestrator": RequestStatus.PENDING,
    "extraction": RequestStatus.EXTRACTING,
    "research": RequestStatus.RESEARCHING,
    "prompt_generation": RequestStatus.GENERATING_PROMPT,
    "image_generation": RequestStatus.GENERATING_IMAGE,
    "validation": RequestStatus.VALIDATING,
    "facial_compositing": RequestStatus.SWAPPING_FACE,
    "export": RequestStatus.COMPLETED,
}

# Keys excluded from per-node state snapshots (noisy, large, or redundant)
_SNAPSHOT_EXCLUDE = frozenset({
    "llm_calls", "agent_trace", "request_id", "error",
    "should_regenerate", "retry_count",
})


class RequestStateProjector:
    """Maps LangGraph node output state to DB update kwargs."""

    def status_for(self, agent: str) -> RequestStatus:
        return _STATUS_MAP.get(agent, RequestStatus.PENDING)

    def project(self, node_state: dict[str, Any], current_agent: str) -> dict[str, Any]:
        """Build the kwargs dict for RequestRepository.update from one node's output."""
        kwargs: dict[str, Any] = {
            "status": self.status_for(current_agent),
            "current_agent": current_agent,
            "agent_trace": node_state.get("agent_trace", []),
            "llm_calls": node_state.get("llm_calls", []),
        }
        ext = node_state.get("extraction")
        if ext and ext.get("figure_name"):
            kwargs["extracted_data"] = {
                "figure_name": ext.get("figure_name"),
                "time_period": ext.get("time_period"),
                "region": ext.get("region"),
                "occupation": ext.get("occupation"),
                "alternative_names": ext.get("alternative_names", []),
                "birth_year": ext.get("birth_year", ""),
                "death_year": ext.get("death_year", ""),
                "notable_features": ext.get("notable_features", ""),
                "cultural_context": ext.get("cultural_context", ""),
                "historical_significance": ext.get("historical_significance", ""),
                "associated_locations": ext.get("associated_locations", []),
            }
        res = node_state.get("research")
        if res and res.get("historical_context"):
            kwargs["research_data"] = {
                "historical_context": res.get("historical_context"),
                "clothing_details": res.get("clothing_details"),
                "physical_description": res.get("physical_description"),
            }
        prompt_state = node_state.get("prompt")
        if prompt_state and prompt_state.get("image_prompt"):
            kwargs["generated_prompt"] = prompt_state["image_prompt"]
        return kwargs

    def attach_snapshot(
        self,
        trace: list[dict[str, Any]],
        current_agent: str,
        node_state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Attach a filtered state snapshot to the most recent trace entry for current_agent."""
        snapshot = {k: v for k, v in node_state.items() if k not in _SNAPSHOT_EXCLUDE}
        trace = list(trace)
        for entry in reversed(trace):
            if entry.get("agent") == current_agent and "state_snapshot" not in entry:
                entry["state_snapshot"] = snapshot
                break
        return trace
