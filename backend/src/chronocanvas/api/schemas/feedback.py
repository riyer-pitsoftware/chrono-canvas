import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    step_name: str
    comment: str
    author: str


class FeedbackResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    request_id: uuid.UUID
    step_name: str
    comment: str
    author: str
    created_at: datetime


class FeedbackListResponse(BaseModel):
    items: list[FeedbackResponse] = Field(default_factory=list)
