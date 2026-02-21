import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.admin import (
    HumanReviewRequest,
    HumanReviewResponse,
    UpdateValidationRuleRequest,
    ValidationQueueResponse,
    ValidationRuleResponse,
    ValidationRulesConfig,
    ValidationThresholdRequest,
)
from chronocanvas.db.engine import get_session
from chronocanvas.db.models.image import GeneratedImage
from chronocanvas.db.models.request import GenerationRequest, RequestStatus
from chronocanvas.db.models.validation import ValidationResult
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.db.repositories.validation_rules import (
    AdminSettingRepository,
    ValidationRuleRepository,
)
from chronocanvas.services.queue import ValidationQueueProjector

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Validation Rules ────────────────────────────────────────────────────────


@router.get("/validation/rules", response_model=ValidationRulesConfig)
async def get_validation_rules(session: AsyncSession = Depends(get_session)):
    rule_repo = ValidationRuleRepository(session)
    setting_repo = AdminSettingRepository(session)
    rules = await rule_repo.list_all()
    threshold = await setting_repo.get_pass_threshold()
    return ValidationRulesConfig(
        rules=[ValidationRuleResponse.model_validate(r) for r in rules],
        pass_threshold=threshold,
    )


@router.put("/validation/rules/{rule_id}", response_model=ValidationRuleResponse)
async def update_validation_rule(
    rule_id: uuid.UUID,
    body: UpdateValidationRuleRequest,
    session: AsyncSession = Depends(get_session),
):
    rule_repo = ValidationRuleRepository(session)
    updates: dict = {"weight": body.weight}
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    rule = await rule_repo.update(rule_id, **updates)
    if rule is None:
        raise HTTPException(status_code=404, detail="Validation rule not found")
    await session.commit()
    return ValidationRuleResponse.model_validate(rule)


@router.put("/validation/threshold", response_model=dict)
async def update_pass_threshold(
    body: ValidationThresholdRequest,
    session: AsyncSession = Depends(get_session),
):
    setting_repo = AdminSettingRepository(session)
    await setting_repo.set_pass_threshold(body.pass_threshold)
    await session.commit()
    return {"pass_threshold": body.pass_threshold}


# ── Review Queue ─────────────────────────────────────────────────────────────


@router.get("/validation/queue", response_model=ValidationQueueResponse)
async def get_validation_queue(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    setting_repo = AdminSettingRepository(session)
    threshold = await setting_repo.get_pass_threshold()

    stmt = (
        select(GenerationRequest)
        .where(
            GenerationRequest.status == RequestStatus.COMPLETED,
            GenerationRequest.human_review_status.is_(None),
        )
        .order_by(GenerationRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    requests = list(result.scalars().all())

    projector = ValidationQueueProjector()
    items = []
    for req in requests:
        val_stmt = select(ValidationResult).where(ValidationResult.request_id == req.id)
        val_result = await session.execute(val_stmt)
        val_rows = list(val_result.scalars().all())

        img_stmt = select(GeneratedImage).where(GeneratedImage.request_id == req.id).limit(1)
        img_result = await session.execute(img_stmt)
        img = img_result.scalars().first()

        item = projector.build_item(req, val_rows, threshold, img)
        if item is not None:
            items.append(item)

    return projector.build_response(items)


@router.post("/validation/{request_id}/accept", response_model=HumanReviewResponse)
async def accept_validation(
    request_id: uuid.UUID,
    body: HumanReviewRequest,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    await repo.update(
        request_id,
        human_review_status="accepted",
        human_review_notes=body.notes,
        human_reviewed_at=datetime.now(timezone.utc),
    )
    await session.commit()
    return HumanReviewResponse(
        request_id=request_id,
        status="accepted",
        notes=body.notes,
    )


@router.post("/validation/{request_id}/reject", response_model=HumanReviewResponse)
async def reject_validation(
    request_id: uuid.UUID,
    body: HumanReviewRequest,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    await repo.update(
        request_id,
        human_review_status="rejected",
        human_review_notes=body.notes,
        human_reviewed_at=datetime.now(timezone.utc),
    )
    await session.commit()
    return HumanReviewResponse(
        request_id=request_id,
        status="rejected",
        notes=body.notes,
    )
