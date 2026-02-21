import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.models.image import GeneratedImage
from chronocanvas.db.repositories.base import BaseRepository


class ImageRepository(BaseRepository[GeneratedImage]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, GeneratedImage)

    async def list_by_request(self, request_id: uuid.UUID) -> list[GeneratedImage]:
        stmt = (
            select(GeneratedImage)
            .where(GeneratedImage.request_id == request_id)
            .order_by(GeneratedImage.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_figure(self, figure_id: uuid.UUID) -> list[GeneratedImage]:
        stmt = (
            select(GeneratedImage)
            .where(GeneratedImage.figure_id == figure_id)
            .order_by(GeneratedImage.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
