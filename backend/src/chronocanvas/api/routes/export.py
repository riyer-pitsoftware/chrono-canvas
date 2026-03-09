import io
import json
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.config import settings
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.security import confine_path
from chronocanvas.services.storage import get_storage_backend

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{request_id}/download")
async def download_image(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    repo = ImageRepository(session)
    images = await repo.list_by_request(request_id)
    if not images:
        raise HTTPException(status_code=404, detail="No images found for this request")

    image = images[0]
    file_path = Path(image.file_path)

    # Cloud mode: redirect to signed GCS URL
    backend = get_storage_backend()
    if backend.is_cloud():
        try:
            relative = str(file_path.relative_to(settings.output_dir))
        except ValueError:
            relative = f"{request_id}/{file_path.name}"
        url = await backend.get_url(relative)
        return RedirectResponse(url=url)

    try:
        file_path = confine_path(file_path, Path(settings.output_dir))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        filename=file_path.name,
    )


@router.get("/{request_id}/audio/{scene_index}")
async def download_audio(request_id: uuid.UUID, scene_index: int):
    backend = get_storage_backend()
    if backend.is_cloud():
        relative = f"{request_id}/audio/scene_{scene_index}.wav"
        url = await backend.get_url(relative)
        return RedirectResponse(url=url)

    audio_path = Path(settings.output_dir) / str(request_id) / "audio" / f"scene_{scene_index}.wav"
    try:
        audio_path = confine_path(audio_path, Path(settings.output_dir))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=audio_path.name,
    )


@router.get("/{request_id}/video")
async def download_video(request_id: uuid.UUID):
    backend = get_storage_backend()
    if backend.is_cloud():
        relative = f"{request_id}/export/storyboard.mp4"
        url = await backend.get_url(relative)
        return RedirectResponse(url=url)

    video_path = Path(settings.output_dir) / str(request_id) / "export" / "storyboard.mp4"
    try:
        video_path = confine_path(video_path, Path(settings.output_dir))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not yet available")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"storyboard_{request_id}.mp4",
    )


@router.get("/{request_id}/metadata")
async def get_export_metadata(request_id: uuid.UUID):
    export_dir = Path(settings.output_dir) / str(request_id) / "export"
    metadata_path = export_dir / "metadata.json"
    try:
        metadata_path = confine_path(metadata_path, Path(settings.output_dir))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Export metadata not found")

    return json.loads(metadata_path.read_text())


@router.get("/{request_id}/bundle")
async def download_bundle(
    request_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """Download a zip bundle containing citations.json, story.md, and scene frames."""
    repo = RequestRepository(session)
    gen_request = await repo.get(request_id)
    if gen_request is None:
        raise HTTPException(status_code=404, detail="Generation request not found")

    storyboard_data = gen_request.storyboard_data or {}
    research_data = gen_request.research_data or {}
    panels = storyboard_data.get("panels", [])

    # --- Build citations.json ---
    citations = list(research_data.get("citations", []))
    for panel in panels:
        for cite in panel.get("citations", []):
            if cite not in citations:
                citations.append(cite)
    for cite in storyboard_data.get("citations", []):
        if cite not in citations:
            citations.append(cite)

    citations_json = json.dumps(citations, indent=2, ensure_ascii=False)

    # --- Build story.md ---
    title = gen_request.input_text or "Untitled Story"
    title_line = title if len(title) <= 120 else title[:117] + "..."
    md_parts = [f"# {title_line}\n"]

    for i, panel in enumerate(panels, start=1):
        md_parts.append(f"## Scene {i}")

        narration = panel.get("narration_text", "")
        if narration:
            md_parts.append(f"> {narration}\n")

        description = panel.get("description", "")
        if description:
            md_parts.append(f"{description}\n")

        characters = panel.get("characters")
        if characters:
            if isinstance(characters, list):
                characters = ", ".join(str(c) for c in characters)
            md_parts.append(f"**Characters**: {characters}")

        mood = panel.get("mood", "")
        if mood:
            md_parts.append(f"**Mood**: {mood}")

        setting = panel.get("setting", "")
        if setting:
            md_parts.append(f"**Setting**: {setting}")

        md_parts.append("\n---\n")

    story_md = "\n".join(md_parts)

    # --- Build zip in memory ---
    output_base = Path(settings.output_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("citations.json", citations_json)
        zf.writestr("story.md", story_md)

        for i, panel in enumerate(panels):
            image_path_str = panel.get("image_path")
            if not image_path_str:
                image_path_str = str(
                    output_base / str(request_id) / f"scene_{i}.png"
                )

            image_path = Path(image_path_str)
            if not image_path.is_absolute():
                image_path = output_base / image_path

            try:
                image_path = confine_path(image_path, output_base)
            except PermissionError:
                continue

            if image_path.exists():
                arcname = f"frames/{image_path.name}"
                zf.write(image_path, arcname)

    buf.seek(0)
    filename = f"chrononoir_bundle_{request_id}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
