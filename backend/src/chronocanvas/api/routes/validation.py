import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.validation import ValidationSummary
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.db.repositories.validation_rules import AdminSettingRepository
from chronocanvas.db.repositories.validations import ValidationRepository
from chronocanvas.services.validation import build_summary

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

    threshold = await AdminSettingRepository(session).get_pass_threshold()

    return build_summary(request_id, results, threshold)
