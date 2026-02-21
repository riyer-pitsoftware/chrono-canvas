import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ValidationRuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    category: str
    display_name: str
    weight: float
    description: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class UpdateValidationRuleRequest(BaseModel):
    weight: float = Field(..., ge=0.0, le=1.0)
    enabled: bool | None = None


class ValidationThresholdRequest(BaseModel):
    pass_threshold: float = Field(..., ge=0.0, le=100.0)


class ValidationRulesConfig(BaseModel):
    rules: list[ValidationRuleResponse]
    pass_threshold: float


class ValidationQueueCategory(BaseModel):
    category: str
    rule_name: str
    score: float
    passed: bool
    details: str | None = None


class ValidationQueueItem(BaseModel):
    request_id: uuid.UUID
    input_text: str
    figure_name: str | None = None
    overall_score: float
    categories: list[ValidationQueueCategory] = Field(default_factory=list)
    image_url: str | None = None
    human_review_status: str | None = None
    created_at: datetime


class ValidationQueueResponse(BaseModel):
    items: list[ValidationQueueItem]
    total: int


class HumanReviewRequest(BaseModel):
    notes: str | None = None


class HumanReviewResponse(BaseModel):
    request_id: uuid.UUID
    status: str
    notes: str | None = None
