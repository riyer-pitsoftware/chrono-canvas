import uuid
from datetime import datetime

from pydantic import BaseModel


class FigureCreate(BaseModel):
    name: str
    birth_year: int | None = None
    death_year: int | None = None
    period_id: uuid.UUID | None = None
    nationality: str | None = None
    occupation: str | None = None
    description: str | None = None
    physical_description: str | None = None
    clothing_notes: str | None = None
    metadata_json: dict | None = None


class FigureUpdate(BaseModel):
    name: str | None = None
    birth_year: int | None = None
    death_year: int | None = None
    period_id: uuid.UUID | None = None
    nationality: str | None = None
    occupation: str | None = None
    description: str | None = None
    physical_description: str | None = None
    clothing_notes: str | None = None
    metadata_json: dict | None = None


class FigureResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    birth_year: int | None = None
    death_year: int | None = None
    period_id: uuid.UUID | None = None
    nationality: str | None = None
    occupation: str | None = None
    description: str | None = None
    physical_description: str | None = None
    clothing_notes: str | None = None
    metadata_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class FigureListResponse(BaseModel):
    items: list[FigureResponse]
    total: int
    offset: int
    limit: int
