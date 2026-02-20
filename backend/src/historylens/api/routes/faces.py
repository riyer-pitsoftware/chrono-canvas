import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from historylens.config import settings

router = APIRouter(prefix="/faces", tags=["faces"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload")
async def upload_face(file: UploadFile):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WebP",
        )

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit")

    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map[file.content_type]
    face_id = uuid.uuid4().hex
    filename = f"{face_id}.{ext}"

    faces_dir = Path(settings.upload_dir) / "faces"
    faces_dir.mkdir(parents=True, exist_ok=True)

    file_path = faces_dir / filename
    file_path.write_bytes(data)

    return {"face_id": face_id, "file_path": str(file_path)}
