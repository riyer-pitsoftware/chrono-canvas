from chronocanvas.agents.state import AgentState


def should_continue_after_orchestrator(state: AgentState) -> str:
    """Short-circuit to END if orchestrator set an error (e.g. content policy)."""
    if state.get("error"):
        return "error"
    return "continue"


def should_continue_after_validation(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    return "continue"


def should_continue_after_image(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    return "validate"
