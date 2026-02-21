from fastapi import APIRouter

from chronocanvas.api.schemas.agents import (
    AgentListResponse,
    AgentStatusResponse,
    CostSummaryResponse,
    LLMAvailabilityResponse,
)
from chronocanvas.llm.router import llm_router

router = APIRouter(prefix="/agents", tags=["agents"])

AGENT_DESCRIPTIONS = {
    "orchestrator": "Coordinates the pipeline and manages agent flow",
    "extraction": "Extracts historical figure details from input text",
    "research": "Researches historical context, clothing, and appearance",
    "prompt_generation": "Creates detailed image generation prompts",
    "image_generation": "Generates portrait images using configured provider",
    "validation": "Validates historical accuracy of generated output",
    "export": "Packages final results for download",
}


@router.get("", response_model=AgentListResponse)
async def list_agents():
    agents = [
        AgentStatusResponse(name=name, description=desc, status="available")
        for name, desc in AGENT_DESCRIPTIONS.items()
    ]
    return AgentListResponse(agents=agents)


@router.get("/llm-status", response_model=LLMAvailabilityResponse)
async def llm_availability():
    availability = await llm_router.check_availability()
    return LLMAvailabilityResponse(providers=availability)


@router.get("/costs", response_model=CostSummaryResponse)
async def cost_summary():
    summary = llm_router.cost_tracker.summary()
    return CostSummaryResponse(**summary)
