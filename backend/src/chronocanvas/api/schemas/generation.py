import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GenerationCreate(BaseModel):
    input_text: str
    figure_id: uuid.UUID | None = None
    provider_override: str | None = None
    face_id: str | None = None


class GenerationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    figure_id: uuid.UUID | None = None
    input_text: str
    status: str
    current_agent: str | None = None
    extracted_data: dict | None = None
    research_data: dict | None = None
    generated_prompt: str | None = None
    error_message: str | None = None
    agent_trace: list[dict[str, Any]] | None = None
    llm_calls: list[dict[str, Any]] | None = None
    llm_costs: dict | None = None
    created_at: datetime
    updated_at: datetime


class GenerationListResponse(BaseModel):
    items: list[GenerationResponse]
    total: int


class ImageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    request_id: uuid.UUID
    figure_id: uuid.UUID | None = None
    file_path: str
    thumbnail_path: str | None = None
    prompt_used: str | None = None
    provider: str
    width: int
    height: int
    validation_score: float | None = None
    created_at: datetime


class BatchGenerationCreate(BaseModel):
    items: list[GenerationCreate]


class BatchGenerationResponse(BaseModel):
    request_ids: list[uuid.UUID]
    total: int


class LLMCallDetail(BaseModel):
    agent: str
    timestamp: float
    system_prompt: str | None = None
    user_prompt: str | None = None
    raw_response: str | None = None
    parsed_output: Any = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    duration_ms: float = 0.0


class ValidationCategoryDetail(BaseModel):
    category: str
    rule_name: str
    passed: bool
    score: float
    details: str | None = None
    reasoning: str | None = None


class StateSnapshot(BaseModel):
    agent: str
    snapshot: dict[str, Any]


class AuditDetailResponse(BaseModel):
    id: uuid.UUID
    input_text: str
    status: str
    current_agent: str | None = None
    figure_name: str | None = None
    created_at: datetime
    updated_at: datetime
    extracted_data: dict | None = None
    research_data: dict | None = None
    generated_prompt: str | None = None
    error_message: str | None = None
    total_cost: float = 0.0
    total_duration_ms: float = 0.0
    llm_calls: list[LLMCallDetail] = []
    validation_score: float | None = None
    validation_passed: bool | None = None
    validation_reasoning: str | None = None
    validation_categories: list[ValidationCategoryDetail] = []
    images: list[ImageResponse] = []
    state_snapshots: list[StateSnapshot] = []
    agent_trace: list[dict[str, Any]] = []
