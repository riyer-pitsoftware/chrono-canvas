"""Cloud storage abstraction — local filesystem for dev, GCS for Cloud Run.

On Cloud Run (detected via K_SERVICE env var or DEPLOYMENT_MODE=gcp),
uploads files to GCS and returns signed URLs. Locally, returns paths as-is.
"""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from chronocanvas.config import settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, local_path: str, remote_key: str) -> str:
        """Upload a local file and return a public/signed URL."""
        ...

    @abstractmethod
    async def get_url(self, remote_key: str) -> str:
        """Get a URL for an already-uploaded file."""
        ...

    @abstractmethod
    def is_cloud(self) -> bool: ...

    async def download(self, remote_key: str) -> bytes | None:
        """Download file contents. Returns None if not found."""
        return None


class LocalStorage(StorageBackend):
    """No-op storage — returns local paths for Docker dev."""

    async def upload(self, local_path: str, remote_key: str) -> str:
        return local_path

    async def get_url(self, remote_key: str) -> str:
        return f"/output/{remote_key}"

    def is_cloud(self) -> bool:
        return False


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend with signed URLs."""

    def __init__(self, bucket_name: str, project_id: str = ""):
        from google.cloud import storage as gcs

        self._client = gcs.Client(project=project_id or None)
        self._bucket = self._client.bucket(bucket_name)
        self._bucket_name = bucket_name
        logger.info("GCS storage initialized: bucket=%s", bucket_name)

    async def upload(self, local_path: str, remote_key: str) -> str:
        """Upload file to GCS and return the gs:// path."""
        blob = self._bucket.blob(remote_key)

        # Detect content type
        suffix = Path(local_path).suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
            ".json": "application/json",
            ".zip": "application/zip",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        blob.upload_from_filename(local_path, content_type=content_type)
        logger.debug("Uploaded %s → gs://%s/%s", local_path, self._bucket_name, remote_key)
        return f"gs://{self._bucket_name}/{remote_key}"

    async def get_url(self, remote_key: str) -> str:
        """Return a gs:// URI — actual serving is done via blob proxy in main.py."""
        return f"gs://{self._bucket_name}/{remote_key}"

    def is_cloud(self) -> bool:
        return True

    async def download(self, remote_key: str) -> bytes | None:
        """Download blob contents from GCS."""
        try:
            blob = self._bucket.blob(remote_key)
            return blob.download_as_bytes()
        except Exception as e:
            logger.warning("GCS download failed for %s: %s", remote_key, e)
            return None


# Singleton
_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Get the storage backend, auto-detecting Cloud Run."""
    global _backend
    if _backend is not None:
        return _backend

    is_cloud_run = bool(os.environ.get("K_SERVICE"))
    is_gcp_mode = settings.deployment_mode == "gcp"
    has_bucket = bool(settings.gcs_bucket)

    if (is_cloud_run or is_gcp_mode) and has_bucket:
        try:
            _backend = GCSStorage(
                bucket_name=settings.gcs_bucket,
                project_id=settings.gcp_project_id,
            )
            return _backend
        except Exception as e:
            logger.error("Failed to initialize GCS storage, falling back to local: %s", e)

    _backend = LocalStorage()
    return _backend


async def upload_artifact(local_path: str, request_id: str, relative_path: str = "") -> str:
    """Convenience: upload an artifact and return its URL.

    Args:
        local_path: Absolute path to the file on disk
        request_id: Generation request ID
        relative_path: Optional sub-path within the request dir.
            If empty, derived from local_path relative to output_dir.
    """
    backend = get_storage_backend()
    if not backend.is_cloud():
        return local_path

    if not relative_path:
        try:
            relative_path = str(Path(local_path).relative_to(settings.output_dir))
        except ValueError:
            relative_path = f"{request_id}/{Path(local_path).name}"

    return await backend.upload(local_path, relative_path)
