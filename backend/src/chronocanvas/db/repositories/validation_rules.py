from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.models.validation_rule import AdminSetting, ValidationRule
from chronocanvas.db.repositories.base import BaseRepository

_PASS_THRESHOLD_KEY = "validation_pass_threshold"
_DEFAULT_THRESHOLD = 70.0


class ValidationRuleRepository(BaseRepository[ValidationRule]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ValidationRule)

    async def list_all(self) -> list[ValidationRule]:
        stmt = select(ValidationRule).order_by(ValidationRule.category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(self, category: str) -> ValidationRule | None:
        stmt = select(ValidationRule).where(ValidationRule.category == category)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_weights(self) -> dict[str, float]:
        """Return {category: weight} for all enabled rules."""
        rules = await self.list_all()
        return {r.category: r.weight for r in rules if r.enabled}


class AdminSettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> str | None:
        obj = await self.session.get(AdminSetting, key)
        return obj.value if obj else None

    async def set(self, key: str, value: str) -> None:
        obj = await self.session.get(AdminSetting, key)
        if obj is None:
            obj = AdminSetting(key=key, value=value)
            self.session.add(obj)
        else:
            obj.value = value
        await self.session.flush()

    async def get_pass_threshold(self) -> float:
        raw = await self.get(_PASS_THRESHOLD_KEY)
        try:
            return float(raw) if raw is not None else _DEFAULT_THRESHOLD
        except ValueError:
            return _DEFAULT_THRESHOLD

    async def set_pass_threshold(self, threshold: float) -> None:
        await self.set(_PASS_THRESHOLD_KEY, str(threshold))
