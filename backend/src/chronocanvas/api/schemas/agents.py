from pydantic import BaseModel


class AgentStatusResponse(BaseModel):
    name: str
    description: str
    status: str


class AgentListResponse(BaseModel):
    agents: list[AgentStatusResponse]


class LLMAvailabilityResponse(BaseModel):
    providers: dict[str, bool]


class CostSummaryResponse(BaseModel):
    total_cost: float
    total_tokens: int
    by_provider: dict[str, float]
    num_calls: int
