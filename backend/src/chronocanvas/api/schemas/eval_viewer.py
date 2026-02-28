"""Pydantic response models for the eval viewer API."""

from __future__ import annotations

from pydantic import BaseModel


class EvalRunSummary(BaseModel):
    run_id: str
    case_id: str
    condition: str
    success: bool
    image_url: str | None = None
    title: str
    has_rating: bool
    rejected: bool = False


class RejectRequest(BaseModel):
    reason: str | None = None


class EvalRunDetail(EvalRunSummary):
    manifest: dict
    rating: dict | None = None
    output_text: str | None = None


class EvalCase(BaseModel):
    case_id: str
    title: str
    subject_type: str
    region: str
    time_period_label: str
    runs: list[EvalRunSummary] = []


class DimensionAggregate(BaseModel):
    condition: str
    dimension: str
    mean: float
    median: float
    n: int


class DashboardData(BaseModel):
    conditions: list[dict]
    dimension_scores: list[DimensionAggregate]
    failure_tags: list[dict]
    total_runs: int
    total_rated: int
