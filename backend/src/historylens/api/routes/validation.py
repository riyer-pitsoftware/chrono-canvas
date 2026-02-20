import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from historylens.api.schemas.validation import ValidationResponse, ValidationSummary
from historylens.db.engine import get_session
from historylens.db.repositories.requests import RequestRepository
from historylens.db.repositories.validations import ValidationRepository

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/{request_id}", response_model=ValidationSummary)
async def get_validation_results(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    req_repo = RequestRepository(session)
    request = await req_repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    val_repo = ValidationRepository(session)
    results = await val_repo.list_by_request(request_id)

    scores = [r.score for r in results] if results else [0.0]
    overall = sum(scores) / len(scores)

    return ValidationSummary(
        request_id=request_id,
        overall_score=overall,
        passed=overall >= 70.0,
        results=[ValidationResponse.model_validate(r) for r in results],
    )
