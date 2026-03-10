"""Archive old generation output directories to save disk space.

Compresses output/{request_id}/ into archive/{request_id}.tar.gz,
updates the DB status to 'archived', and removes the original files.
"""

import logging
import shutil
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.config import settings
from chronocanvas.db.models.request import GenerationRequest, RequestStatus

logger = logging.getLogger(__name__)


async def archive_old_requests(
    session: AsyncSession,
    older_than_days: int = 2,
    dry_run: bool = False,
) -> dict:
    """Archive generation requests older than `older_than_days`.

    Returns a summary dict with counts and details.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    output_dir = Path(settings.output_dir).resolve()
    archive_dir = Path(settings.archive_dir).resolve()

    # Find eligible requests: completed or failed, older than cutoff, not already archived
    stmt = (
        select(GenerationRequest)
        .where(
            GenerationRequest.created_at < cutoff,
            GenerationRequest.status.in_(
                [
                    RequestStatus.COMPLETED,
                    RequestStatus.FAILED,
                ]
            ),
        )
        .order_by(GenerationRequest.created_at.asc())
    )
    result = await session.execute(stmt)
    requests = list(result.scalars().all())

    if not requests:
        return {"archived": 0, "skipped": 0, "errors": 0, "details": []}

    archive_dir.mkdir(parents=True, exist_ok=True)
    archived = 0
    skipped = 0
    errors = 0
    details: list[dict] = []

    for req in requests:
        req_dir = output_dir / str(req.id)

        if not req_dir.exists():
            # No output directory on disk — just mark archived in DB
            if not dry_run:
                req.status = RequestStatus.ARCHIVED
            details.append(
                {"id": str(req.id), "action": "marked_archived", "reason": "no output dir"}
            )
            archived += 1
            continue

        archive_path = archive_dir / f"{req.id}.tar.gz"

        if archive_path.exists():
            details.append(
                {"id": str(req.id), "action": "skipped", "reason": "archive already exists"}
            )
            skipped += 1
            continue

        if dry_run:
            dir_size = sum(f.stat().st_size for f in req_dir.rglob("*") if f.is_file())
            details.append(
                {
                    "id": str(req.id),
                    "action": "would_archive",
                    "size_mb": round(dir_size / 1_048_576, 2),
                    "created_at": req.created_at.isoformat(),
                }
            )
            archived += 1
            continue

        try:
            # Compress to tar.gz
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(str(req_dir), arcname=str(req.id))

            dir_size = sum(f.stat().st_size for f in req_dir.rglob("*") if f.is_file())

            # Remove original directory
            shutil.rmtree(req_dir)

            # Update DB status
            req.status = RequestStatus.ARCHIVED

            details.append(
                {
                    "id": str(req.id),
                    "action": "archived",
                    "size_mb": round(dir_size / 1_048_576, 2),
                    "archive": str(archive_path),
                }
            )
            archived += 1
            logger.info("Archived request %s (%.2f MB)", req.id, dir_size / 1_048_576)

        except Exception:
            logger.exception("Failed to archive request %s", req.id)
            # Clean up partial archive
            if archive_path.exists():
                archive_path.unlink()
            details.append({"id": str(req.id), "action": "error"})
            errors += 1

    if not dry_run:
        await session.commit()

    return {
        "archived": archived,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }
