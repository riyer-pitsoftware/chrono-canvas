import glob
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.generation import (
    AuditDetailResponse,
    BatchGenerationCreate,
    BatchGenerationResponse,
    GenerationCreate,
    GenerationListResponse,
    GenerationResponse,
    ImageResponse,
    LLMCallDetail,
    StateSnapshot,
    ValidationCategoryDetail,
)
from chronocanvas.config import settings
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.services.generation import (
    VALID_RETRY_STEPS,
    retry_generation_pipeline,
    run_generation_pipeline,
)

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerationResponse, status_code=201)
async def create_generation(
    data: GenerationCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    request = await repo.create(
        input_text=data.input_text,
        figure_id=data.figure_id,
        status="pending",
    )
    await session.commit()

    source_face_path: str | None = None
    if data.face_id:
        matches = glob.glob(str(Path(settings.upload_dir) / "faces" / f"{data.face_id}.*"))
        if not matches:
            raise HTTPException(status_code=404, detail="Face not found")
        source_face_path = matches[0]

    background_tasks.add_task(
        run_generation_pipeline, str(request.id), data.input_text,
        source_face_path=source_face_path,
    )

    return GenerationResponse.model_validate(request)


@router.post("/batch", response_model=BatchGenerationResponse, status_code=201)
async def create_batch_generation(
    data: BatchGenerationCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    request_ids = []
    for item in data.items:
        request = await repo.create(
            input_text=item.input_text,
            figure_id=item.figure_id,
            status="pending",
        )
        request_ids.append(request.id)
        background_tasks.add_task(run_generation_pipeline, str(request.id), item.input_text)
    await session.commit()

    return BatchGenerationResponse(request_ids=request_ids, total=len(request_ids))


@router.get("", response_model=GenerationListResponse)
async def list_generations(
    offset: int = 0,
    limit: int = 20,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    if status:
        items = await repo.list_by_status(status, offset=offset, limit=limit)
    else:
        items = await repo.list(offset=offset, limit=limit)
    total = await repo.count()
    return GenerationListResponse(
        items=[GenerationResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/{request_id}", response_model=GenerationResponse)
async def get_generation(request_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Generation request not found")
    return GenerationResponse.model_validate(request)


@router.get("/{request_id}/audit", response_model=AuditDetailResponse)
async def get_generation_audit(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    image_repo = ImageRepository(session)
    images = await image_repo.list_by_request(request_id)

    raw_calls = request.llm_calls or []
    llm_calls = [LLMCallDetail(**c) for c in raw_calls]
    total_cost = sum(c.cost for c in llm_calls)
    total_duration = sum(c.duration_ms for c in llm_calls)

    # Extract validation details from the last validation llm_call
    validation_score = None
    validation_passed = None
    validation_reasoning = None
    validation_categories: list[ValidationCategoryDetail] = []

    for call in reversed(raw_calls):
        if call.get("agent") == "validation" and isinstance(call.get("parsed_output"), dict):
            parsed = call["parsed_output"]
            validation_score = parsed.get("overall_score")
            validation_passed = parsed.get("passed")
            validation_reasoning = parsed.get("overall_reasoning")
            for r in parsed.get("results", []):
                validation_categories.append(ValidationCategoryDetail(
                    category=r.get("category", ""),
                    rule_name=r.get("rule_name", ""),
                    passed=r.get("passed", False),
                    score=r.get("score", 0.0),
                    details=r.get("details"),
                    reasoning=r.get("reasoning"),
                ))
            break

    figure_name = None
    if request.extracted_data:
        figure_name = request.extracted_data.get("figure_name")

    state_snapshots = [
        StateSnapshot(agent=entry["agent"], snapshot=entry["state_snapshot"])
        for entry in (request.agent_trace or [])
        if "state_snapshot" in entry
    ]

    return AuditDetailResponse(
        id=request.id,
        input_text=request.input_text,
        status=request.status,
        current_agent=request.current_agent,
        figure_name=figure_name,
        created_at=request.created_at,
        updated_at=request.updated_at,
        extracted_data=request.extracted_data,
        research_data=request.research_data,
        generated_prompt=request.generated_prompt,
        error_message=request.error_message,
        total_cost=total_cost,
        total_duration_ms=total_duration,
        llm_calls=llm_calls,
        validation_score=validation_score,
        validation_passed=validation_passed,
        validation_reasoning=validation_reasoning,
        validation_categories=validation_categories,
        images=[ImageResponse.model_validate(img) for img in images],
        state_snapshots=state_snapshots,
        agent_trace=request.agent_trace or [],
    )


@router.delete("/{request_id}", status_code=204)
async def delete_generation(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    # Remove output files from disk
    output_path = Path(settings.output_dir) / str(request_id)
    if output_path.exists():
        shutil.rmtree(output_path)

    await session.delete(request)
    await session.commit()


@router.get("/{request_id}/images", response_model=list[ImageResponse])
async def get_generation_images(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    repo = ImageRepository(session)
    images = await repo.list_by_request(request_id)
    return [ImageResponse.model_validate(img) for img in images]


@router.post("/{request_id}/retry", response_model=GenerationResponse, status_code=202)
async def retry_generation(
    request_id: uuid.UUID,
    from_step: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    if from_step not in VALID_RETRY_STEPS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid step '{from_step}'. Must be one of: {sorted(VALID_RETRY_STEPS)}",
        )

    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    if request.status not in ("failed", "completed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry a generation with status '{request.status}'",
        )

    background_tasks.add_task(retry_generation_pipeline, str(request_id), from_step)
    return GenerationResponse.model_validate(request)
