from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from historylens.db.models.figure import Figure
from historylens.db.repositories.base import BaseRepository


class FigureRepository(BaseRepository[Figure]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Figure)

    async def search(self, query: str, offset: int = 0, limit: int = 50) -> list[Figure]:
        stmt = (
            select(Figure)
            .where(Figure.name.ilike(f"%{query}%"))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Figure | None:
        stmt = select(Figure).where(Figure.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_period(self, period_id, offset: int = 0, limit: int = 50) -> list[Figure]:
        stmt = (
            select(Figure)
            .where(Figure.period_id == period_id)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
