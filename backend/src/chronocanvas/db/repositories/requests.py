from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.models.request import GenerationRequest, RequestStatus
from chronocanvas.db.repositories.base import BaseRepository


class RequestRepository(BaseRepository[GenerationRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, GenerationRequest)

    async def list(self, offset: int = 0, limit: int = 50) -> list[GenerationRequest]:
        stmt = (
            select(GenerationRequest)
            .order_by(GenerationRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(
        self, status: RequestStatus, offset: int = 0, limit: int = 50
    ) -> list[GenerationRequest]:
        stmt = (
            select(GenerationRequest)
            .where(GenerationRequest.status == status)
            .order_by(GenerationRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 20) -> list[GenerationRequest]:
        stmt = (
            select(GenerationRequest)
            .order_by(GenerationRequest.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
