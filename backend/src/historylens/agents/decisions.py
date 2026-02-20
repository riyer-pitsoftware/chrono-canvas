from historylens.agents.state import AgentState


def should_continue_after_validation(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    if state.get("should_regenerate", False):
        return "regenerate"
    return "continue"


def should_continue_after_image(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    return "validate"
