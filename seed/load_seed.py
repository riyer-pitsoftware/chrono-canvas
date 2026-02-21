"""Load seed data into the database."""
import asyncio
import json
import sys
from pathlib import Path

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession

# Add backend src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from chronocanvas.db.engine import async_session, engine
from chronocanvas.db.base import Base
from chronocanvas.db.models import *  # noqa
from chronocanvas.services.figure import load_figures_from_json

SEED_DIR = Path(__file__).parent


async def load_periods(session: AsyncSession) -> int:
    from chronocanvas.db.models.period import Period
    from sqlalchemy import select

    periods_path = SEED_DIR / "periods.json"
    periods = json.loads(periods_path.read_text())
    count = 0

    for p in periods:
        existing = await session.execute(select(Period).where(Period.name == p["name"]))
        if existing.scalar_one_or_none():
            continue
        period = Period(**p)
        session.add(period)
        count += 1

    await session.flush()
    return count


async def main():
    print("Loading seed data...")

    async with async_session() as session:
        # Load periods
        period_count = await load_periods(session)
        print(f"  Loaded {period_count} periods")

        # Load figures
        figures_path = SEED_DIR / "figures.json"
        figure_count = await load_figures_from_json(session, figures_path)
        print(f"  Loaded {figure_count} figures")

        # Load timeline figures (Indian subcontinent emphasis, 500 BCE–1700 CE)
        timeline_path = SEED_DIR / "timeline_figures.json"
        timeline_count = await load_figures_from_json(session, timeline_path)
        print(f"  Loaded {timeline_count} timeline figures")

        await session.commit()

    print("Seed data loaded successfully!")


if __name__ == "__main__":
    asyncio.run(main())
