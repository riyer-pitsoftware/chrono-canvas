import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.models.validation import ValidationResult
from chronocanvas.db.repositories.base import BaseRepository


class ValidationRepository(BaseRepository[ValidationResult]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ValidationResult)

    async def list_by_request(self, request_id: uuid.UUID) -> list[ValidationResult]:
        stmt = (
            select(ValidationResult)
            .where(ValidationResult.request_id == request_id)
            .order_by(ValidationResult.category)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
