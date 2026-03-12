"""Canonical mapping of LangGraph agent names to RequestStatus values."""

from chronocanvas.db.models.request import RequestStatus

AGENT_STATUS_MAP: dict[str, RequestStatus] = {
    "orchestrator": RequestStatus.PENDING,
    "extraction": RequestStatus.EXTRACTING,
    "research": RequestStatus.RESEARCHING,
    "prompt_generation": RequestStatus.GENERATING_PROMPT,
    "image_generation": RequestStatus.GENERATING_IMAGE,
    "validation": RequestStatus.VALIDATING,
    "facial_compositing": RequestStatus.SWAPPING_FACE,
    "export": RequestStatus.COMPLETED,
}


def status_for_agent(agent: str) -> RequestStatus:
    """Look up the RequestStatus for a given agent name, defaulting to PENDING."""
    return AGENT_STATUS_MAP.get(agent, RequestStatus.PENDING)
