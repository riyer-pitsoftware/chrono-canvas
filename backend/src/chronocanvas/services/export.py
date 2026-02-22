import uuid
import zipfile
from pathlib import Path

from chronocanvas.config import settings


async def create_export_zip(request_id: uuid.UUID) -> Path:
    export_dir = Path(settings.output_dir) / str(request_id) / "export"
    if not export_dir.exists():
        raise FileNotFoundError(f"Export directory not found: {export_dir}")

    zip_path = Path(settings.output_dir) / str(request_id) / f"{request_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in export_dir.iterdir():
            zf.write(file, file.name)

    return zip_path
