"""Eval viewer API routes — browse eval runs, cases, and dashboard data."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from chronocanvas.api.schemas.eval_viewer import (
    DashboardData,
    EvalCase,
    EvalRunDetail,
    EvalRunSummary,
)
from chronocanvas.services.eval_data import (
    get_case,
    get_dashboard,
    get_run,
    list_cases,
    list_runs,
)

router = APIRouter(prefix="/eval", tags=["eval"])


@router.get("/runs", response_model=list[EvalRunSummary])
async def get_eval_runs(
    condition: str | None = Query(None),
    case_id: str | None = Query(None),
):
    """List eval runs, optionally filtered by condition or case."""
    return list_runs(condition=condition, case_id=case_id)


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(run_id: str):
    """Get detailed info for a single eval run."""
    result = get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/cases", response_model=list[EvalCase])
async def get_eval_cases():
    """List all eval cases with their run summaries."""
    return list_cases()


@router.get("/cases/{case_id}", response_model=EvalCase)
async def get_eval_case(case_id: str):
    """Get a single eval case with all its runs."""
    result = get_case(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@router.get("/dashboard", response_model=DashboardData)
async def get_eval_dashboard():
    """Get aggregated dashboard data across all conditions."""
    return get_dashboard()
