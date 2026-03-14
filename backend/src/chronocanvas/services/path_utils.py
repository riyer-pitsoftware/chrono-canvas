"""Shared helpers for converting filesystem paths to browser-usable URLs."""

from chronocanvas.config import settings


def file_path_to_url(file_path: str) -> str | None:
    """Convert a filesystem path to a URL served via StaticFiles mount at /output/."""
    if not file_path:
        return None
    output_dir = str(settings.output_dir).rstrip("/")
    rel = file_path.replace(output_dir, "").lstrip("/")
    return f"/output/{rel}" if rel else None
