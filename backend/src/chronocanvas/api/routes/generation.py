import glob
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.feedback import (
    CreateFeedbackRequest,
    FeedbackListResponse,
    FeedbackResponse,
)
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
from chronocanvas.db.repositories.feedback import FeedbackRepository
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
    # For image-to-story, text is optional (Gemini extracts from image)
    if data.input_text:
        is_safe, reason = check_input(data.input_text)
        if not is_safe:
            raise HTTPException(status_code=422, detail=reason)

    # Require either text or image input
    if not data.input_text.strip() and not data.ref_image_id:
        raise HTTPException(status_code=422, detail="Provide either text or an image")

    repo = RequestRepository(session)
    gen_request = await repo.create(
        input_text=data.input_text,
        figure_id=data.figure_id,
        run_type=data.run_type,
        status="pending",
    )
    await session.commit()

    if data.run_type == "creative_story":
        # Resolve optional reference image for image-to-story
        ref_image_path: str | None = None
        ref_image_mime: str | None = None
        if data.ref_image_id:
            refs_base = Path(settings.upload_dir) / "references"
            matches = glob.glob(str(refs_base / f"{data.ref_image_id}.*"))
            safe_matches = []
            for m in matches:
                try:
                    confine_path(Path(m), refs_base)
                    safe_matches.append(m)
                except PermissionError:
                    pass
            if not safe_matches:
                raise HTTPException(status_code=404, detail="Reference image not found")
            ref_image_path = safe_matches[0]
            ext = Path(ref_image_path).suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
            ref_image_mime = mime_map.get(ext, "image/png")

        # Resolve optional reference images for style/location refs
        ref_images_data: list[dict] | None = None
        if data.ref_image_ids:
            ref_images_data = []
            refs_base = Path(settings.upload_dir) / "references"
            for rid in data.ref_image_ids[:5]:  # max 5
                matches = glob.glob(str(refs_base / f"{rid}.*"))
                for m in matches:
                    try:
                        confine_path(Path(m), refs_base)
                        ext = Path(m).suffix.lower()
                        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
                        ref_images_data.append({
                            "file_path": m,
                            "mime_type": mime_map.get(ext, "image/png"),
                            "ref_type": "style_reference",
                        })
                    except PermissionError:
                        pass

        await request.app.state.arq_pool.enqueue_job(
            "run_story_pipeline_task",
            str(gen_request.id), data.input_text,
            ref_image_path=ref_image_path,
            ref_image_mime=ref_image_mime,
            ref_images=ref_images_data,
            config_payload=data.config,
        )
    else:
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
            config_payload=data.config,
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
    from chronocanvas.config import settings

    if not settings.enable_audit_ui:
        raise HTTPException(status_code=404, detail="Not found")
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


@router.post("/{request_id}/scenes/{scene_index}/edit", status_code=202)
async def edit_scene(
    request_id: uuid.UUID,
    scene_index: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    instruction: str = "",
):
    if not settings.scene_editing_enabled:
        raise HTTPException(status_code=503, detail="Scene editing is disabled")
    if not instruction.strip():
        raise HTTPException(status_code=422, detail="Edit instruction is required")

    repo = RequestRepository(session)
    gen_request = await repo.get(request_id)
    if not gen_request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    if gen_request.run_type != "creative_story":
        raise HTTPException(status_code=422, detail="Scene editing only available for story mode")

    await request.app.state.arq_pool.enqueue_job(
        "edit_scene_task",
        str(request_id), scene_index, instruction,
    )
    return {"status": "editing", "scene_index": scene_index}


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


@router.post("/{request_id}/feedback", response_model=FeedbackResponse, status_code=201)
async def create_feedback(
    request_id: uuid.UUID,
    data: CreateFeedbackRequest,
    session: AsyncSession = Depends(get_session),
):
    req_repo = RequestRepository(session)
    gen_request = await req_repo.get(request_id)
    if not gen_request:
        raise HTTPException(status_code=404, detail="Generation request not found")

    repo = FeedbackRepository(session)
    feedback = await repo.create(
        request_id=request_id,
        step_name=data.step_name,
        comment=data.comment,
        author=data.author,
    )
    await session.commit()
    return FeedbackResponse.model_validate(feedback)


@router.get("/{request_id}/feedback", response_model=FeedbackListResponse)
async def list_feedback(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    repo = FeedbackRepository(session)
    items = await repo.list_by_request(request_id)
    return FeedbackListResponse(
        items=[FeedbackResponse.model_validate(f) for f in items]
    )
