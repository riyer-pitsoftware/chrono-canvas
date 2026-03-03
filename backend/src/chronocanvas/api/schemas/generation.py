import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GenerationCreate(BaseModel):
    input_text: str = ""
    figure_id: uuid.UUID | None = None
    provider_override: str | None = None
    # face_id must be the 32-char lowercase hex produced by the upload endpoint
    # (uuid4().hex).  This pattern rejects path-traversal strings before they
    # reach the filesystem.
    face_id: str | None = Field(None, pattern=r"^[0-9a-f]{32}$")
    run_type: str = "portrait"
    # Optional reference image for image-to-story (32-char hex from upload endpoint)
    ref_image_id: str | None = Field(None, pattern=r"^[0-9a-f]{32}$")
    # Optional reference images for style/location/character refs
    ref_image_ids: list[str] | None = None


class GenerationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    figure_id: uuid.UUID | None = None
    input_text: str
    run_type: str = "portrait"
    status: str
    current_agent: str | None = None
    extracted_data: dict | None = None
    research_data: dict | None = None
    generated_prompt: str | None = None
    error_message: str | None = None
    agent_trace: list[dict[str, Any]] | None = None
    llm_calls: list[dict[str, Any]] | None = None
    llm_costs: dict | None = None
    storyboard_data: dict | None = None
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
    requested_provider: str | None = None
    fallback: bool = False


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
    llm_calls: list[LLMCallDetail] = Field(default_factory=list)
    validation_score: float | None = None
    validation_passed: bool | None = None
    validation_reasoning: str | None = None
    validation_categories: list[ValidationCategoryDetail] = Field(default_factory=list)
    images: list[ImageResponse] = Field(default_factory=list)
    state_snapshots: list[StateSnapshot] = Field(default_factory=list)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    storyboard_data: dict[str, Any] | None = None
    run_type: str = "portrait"
