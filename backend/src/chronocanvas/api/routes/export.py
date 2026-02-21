import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.config import settings
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.images import ImageRepository

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
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        filename=file_path.name,
    )


@router.get("/{request_id}/metadata")
async def get_export_metadata(request_id: uuid.UUID):
    export_dir = Path(settings.output_dir) / str(request_id) / "export"
    metadata_path = export_dir / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Export metadata not found")

    import json

    return json.loads(metadata_path.read_text())
