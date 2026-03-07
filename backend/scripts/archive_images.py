#!/usr/bin/env python3
"""Archive old generation output to save disk space.

Usage:
    python scripts/archive_images.py                  # archive requests > 2 days old
    python scripts/archive_images.py --days 7         # archive requests > 7 days old
    python scripts/archive_images.py --dry-run        # preview without changes
    python scripts/archive_images.py --days 0         # archive ALL completed/failed requests

Via Docker:
    docker exec chrono-canvas-api-1 python /app/scripts/archive_images.py --dry-run
    docker exec chrono-canvas-api-1 python /app/scripts/archive_images.py --days 2
"""

import argparse
import asyncio
import sys

# Ensure the package is importable when run from project root
sys.path.insert(0, "src")


async def main(days: int, dry_run: bool) -> None:
    from chronocanvas.db.engine import async_session
    from chronocanvas.services.archiver import archive_old_requests

    async with async_session() as session:
        result = await archive_old_requests(session, older_than_days=days, dry_run=dry_run)

    mode = "DRY RUN" if dry_run else "ARCHIVE"
    print(f"\n[{mode}] older_than_days={days}")
    print(f"  Archived: {result['archived']}")
    print(f"  Skipped:  {result['skipped']}")
    print(f"  Errors:   {result['errors']}")

    for d in result["details"]:
        size = f" ({d['size_mb']} MB)" if "size_mb" in d else ""
        reason = f" — {d.get('reason', '')}" if d.get("reason") else ""
        print(f"  {d['action']:20s} {d['id']}{size}{reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive old generation outputs")
    parser.add_argument("--days", type=int, default=2, help="Archive requests older than N days (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.dry_run))
