import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.models.feedback import AuditFeedback
from chronocanvas.db.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[AuditFeedback]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditFeedback)

    async def list_by_request(self, request_id: uuid.UUID) -> list[AuditFeedback]:
        stmt = (
            select(AuditFeedback)
            .where(AuditFeedback.request_id == request_id)
            .order_by(AuditFeedback.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
