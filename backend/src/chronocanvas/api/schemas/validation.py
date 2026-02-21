import uuid
from datetime import datetime

from pydantic import BaseModel


class ValidationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    request_id: uuid.UUID
    category: str
    rule_name: str
    passed: bool
    score: float
    details: str | None = None
    suggestions: list | None = None
    created_at: datetime


class ValidationSummary(BaseModel):
    request_id: uuid.UUID
    overall_score: float
    passed: bool
    results: list[ValidationResponse]
