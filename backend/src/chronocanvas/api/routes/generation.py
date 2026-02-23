import glob
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.generation import (
    AuditDetailResponse,
    BatchGenerationCreate,
    BatchGenerationResponse,
    GenerationCreate,
    GenerationListResponse,
    GenerationResponse,
    ImageResponse,
)
from chronocanvas.config import settings
from chronocanvas.content_moderation import check_input
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.security import confine_path
from chronocanvas.services.audit import AuditProjector
from chronocanvas.services.generation import VALID_RETRY_STEPS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerationResponse, status_code=201)
async def create_generation(
    data: GenerationCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    is_safe, reason = check_input(data.input_text)
    if not is_safe:
        raise HTTPException(status_code=422, detail=reason)

    repo = RequestRepository(session)
    gen_request = await repo.create(
        input_text=data.input_text,
        figure_id=data.figure_id,
        status="pending",
    )
    await session.commit()

    source_face_path: str | None = None
    if data.face_id:
        faces_base = Path(settings.upload_dir) / "faces"
        matches = glob.glob(str(faces_base / f"{data.face_id}.*"))
        safe_matches = []
        for m in matches:
            try:
                confine_path(Path(m), faces_base)
                safe_matches.append(m)
            except PermissionError:
                pass
        if not safe_matches:
            raise HTTPException(status_code=404, detail="Face not found")
        source_face_path = safe_matches[0]

    await request.app.state.arq_pool.enqueue_job(
        "run_generation_pipeline_task",
        str(gen_request.id), data.input_text,
        source_face_path=source_face_path,
    )

    return GenerationResponse.model_validate(gen_request)


@router.post("/batch", response_model=BatchGenerationResponse, status_code=201)
async def create_batch_generation(
    data: BatchGenerationCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    request_ids = []
    for item in data.items:
        gen_request = await repo.create(
            input_text=item.input_text,
            figure_id=item.figure_id,
            status="pending",
        )
        request_ids.append(gen_request.id)
    await session.commit()

    for i, item in enumerate(data.items):
        await request.app.state.arq_pool.enqueue_job(
            "run_generation_pipeline_task", str(request_ids[i]), item.input_text
        )

    return BatchGenerationResponse(request_ids=request_ids, total=len(request_ids))


@router.get("", response_model=GenerationListResponse)
async def list_generations(
    offset: int = 0,
    limit: int = 20,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = RequestRepository(session)
    status_filter = status if status else None
    if status_filter:
        items = await repo.list_by_status(status_filter, offset=offset, limit=limit)
        total = await repo.count(status_filter)
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

    return AuditProjector().project(request, images)


@router.delete("/{request_id}", status_code=204)
async def delete_generation(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    await session.delete(request)
    await session.commit()

    # Best-effort filesystem cleanup after DB delete succeeds
    output_path = Path(settings.output_dir) / str(request_id)
    if output_path.exists():
        try:
            shutil.rmtree(output_path)
        except OSError:
            logger.warning("Failed to clean up output files for %s", request_id, exc_info=True)


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
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    if from_step not in VALID_RETRY_STEPS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid step '{from_step}'. Must be one of: {sorted(VALID_RETRY_STEPS)}",
        )

    repo = RequestRepository(session)
    gen_request = await repo.get(request_id)
    if not gen_request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    if gen_request.status not in ("failed", "completed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry a generation with status '{gen_request.status}'",
        )

    await request.app.state.arq_pool.enqueue_job(
        "retry_generation_pipeline_task", str(request_id), from_step
    )
    return GenerationResponse.model_validate(gen_request)
