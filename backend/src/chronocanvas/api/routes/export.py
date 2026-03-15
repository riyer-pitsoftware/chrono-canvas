import io
import json
import logging
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.config import settings
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.security import confine_path
from chronocanvas.services.storage import StorageBackend, get_storage_backend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


# ── Asset serving helpers ────────────────────────────────────────────────────


@dataclass(frozen=True)
class _CloudAsset:
    """Asset resolved to cloud storage (GCS)."""

    data: bytes


@dataclass(frozen=True)
class _LocalAsset:
    """Asset resolved to a confined local path."""

    path: Path


_AssetSource = _CloudAsset | _LocalAsset


async def resolve_asset_source(
    relative_key: str,
    local_path: Path,
    backend: StorageBackend,
    *,
    not_found_detail: str = "File not found",
) -> _AssetSource:
    """Determine storage backend and resolve the asset to a serveable source.

    Cloud mode: downloads the blob bytes via *backend*.
    Local mode: confines *local_path* inside ``settings.output_dir`` and
    verifies the file exists on disk.

    Raises ``HTTPException`` (403 or 404) on access or existence errors.
    """
    if backend.is_cloud():
        data = await backend.download(relative_key)
        if data is None:
            logger.warning("Asset not found in cloud storage: %s", relative_key)
            raise HTTPException(status_code=404, detail=not_found_detail)
        return _CloudAsset(data=data)

    # Local mode — confine path then verify existence
    try:
        confined = confine_path(local_path, Path(settings.output_dir))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not confined.exists():
        raise HTTPException(status_code=404, detail=not_found_detail)
    return _LocalAsset(path=confined)


def serve_asset_response(
    source: _AssetSource,
    *,
    media_type: str,
    filename: str,
    cache_control: str = "public, max-age=3600",
) -> Response:
    """Return the appropriate FastAPI response for a resolved asset source.

    Cloud assets are served as inline ``Response`` with cache headers.
    Local assets are served via ``FileResponse``.
    """
    if isinstance(source, _CloudAsset):
        return Response(
            content=source.data,
            media_type=media_type,
            headers={"Cache-Control": cache_control},
        )
    return FileResponse(
        path=str(source.path),
        media_type=media_type,
        filename=filename,
    )


# ── Route handlers ───────────────────────────────────────────────────────────


@router.get("/{request_id}/download")
async def download_image(request_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = ImageRepository(session)
    images = await repo.list_by_request(request_id)
    if not images:
        raise HTTPException(status_code=404, detail="No images found for this request")

    image = images[0]
    file_path = Path(image.file_path)

    # Derive the cloud-relative key from the stored path
    try:
        relative_key = str(file_path.relative_to(settings.output_dir))
    except ValueError:
        relative_key = f"{request_id}/{file_path.name}"

    backend = get_storage_backend()

    # Images use redirect for cloud (signed URL) instead of download
    if backend.is_cloud():
        url = await backend.get_url(relative_key)
        return RedirectResponse(url=url)

    source = await resolve_asset_source(
        relative_key,
        file_path,
        backend,
        not_found_detail="Image file not found on disk",
    )
    return serve_asset_response(
        source,
        media_type="image/png",
        filename=file_path.name,
    )


@router.get("/{request_id}/audio/{scene_index}")
async def download_audio(request_id: uuid.UUID, scene_index: int):
    relative_key = f"{request_id}/audio/scene_{scene_index}.wav"
    local_path = Path(settings.output_dir) / str(request_id) / "audio" / f"scene_{scene_index}.wav"
    backend = get_storage_backend()

    source = await resolve_asset_source(
        relative_key,
        local_path,
        backend,
        not_found_detail="Audio file not found",
    )
    return serve_asset_response(
        source,
        media_type="audio/wav",
        filename=f"scene_{scene_index}.wav",
    )


@router.get("/{request_id}/video")
async def download_video(request_id: uuid.UUID):
    relative_key = f"{request_id}/export/storyboard.mp4"
    local_path = Path(settings.output_dir) / str(request_id) / "export" / "storyboard.mp4"
    backend = get_storage_backend()

    source = await resolve_asset_source(
        relative_key,
        local_path,
        backend,
        not_found_detail="Video not yet available",
    )
    return serve_asset_response(
        source,
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
async def download_bundle(request_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
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
                image_path_str = str(output_base / str(request_id) / f"scene_{i}.png")

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
