import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from historylens.db.repositories.figures import FigureRepository

logger = logging.getLogger(__name__)


async def load_figures_from_json(session: AsyncSession, json_path: str | Path) -> int:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    data = json.loads(path.read_text())
    repo = FigureRepository(session)
    count = 0

    for figure_data in data:
        existing = await repo.get_by_name(figure_data["name"])
        if existing:
            continue
        await repo.create(**figure_data)
        count += 1

    await session.flush()
    return count
