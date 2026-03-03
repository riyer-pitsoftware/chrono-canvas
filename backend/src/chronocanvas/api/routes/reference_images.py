"""Reference image upload — shared by Image-to-Story and Reference Image features."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile

from chronocanvas.config import settings
from chronocanvas.security import validate_image_magic

router = APIRouter(prefix="/reference-images", tags=["reference-images"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_REF_TYPES = {"story_source", "location", "character", "artifact", "style_reference"}


@router.post("/upload")
async def upload_reference_image(
    file: UploadFile,
    ref_type: str = Query("story_source", description="Reference type"),
    description: str = Query("", description="Optional description"),
):
    if ref_type not in ALLOWED_REF_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ref_type: {ref_type}. Allowed: {sorted(ALLOWED_REF_TYPES)}",
        )

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WebP",
        )

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit")

    if not validate_image_magic(data):
        raise HTTPException(
            status_code=400,
            detail="File content does not match a supported image format",
        )

    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map[file.content_type]
    ref_id = uuid.uuid4().hex
    filename = f"{ref_id}.{ext}"

    refs_dir = Path(settings.upload_dir) / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    file_path = refs_dir / filename
    file_path.write_bytes(data)

    return {
        "ref_id": ref_id,
        "file_path": str(file_path),
        "mime_type": file.content_type,
        "ref_type": ref_type,
        "description": description,
    }
