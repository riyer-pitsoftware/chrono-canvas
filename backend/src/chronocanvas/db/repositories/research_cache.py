from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.models.research_cache import ResearchCache
from chronocanvas.db.repositories.base import BaseRepository


class ResearchCacheRepository(BaseRepository[ResearchCache]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ResearchCache)

    async def find_similar(
        self, embedding: list[float], threshold: float = 0.85
    ) -> ResearchCache | None:
        """Find most similar cache entry using cosine distance."""
        stmt = (
            select(ResearchCache)
            .order_by(ResearchCache.embedding.cosine_distance(embedding))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        entry = result.scalars().first()
        if entry is None:
            return None
        distance = await self.session.execute(
            select(
                ResearchCache.embedding.cosine_distance(embedding).label("distance")
            ).where(ResearchCache.id == entry.id)
        )
        dist_val = distance.scalar()
        similarity = 1 - dist_val
        return entry if similarity >= threshold else None

    async def record_hit(self, cache_id: str, cost_saved: float) -> None:
        """Increment hit count and record cost savings."""
        entry = await self.get(cache_id)
        if entry:
            entry.hit_count += 1
            entry.last_accessed_at = datetime.now(timezone.utc)
            entry.cost_saved_usd += cost_saved
            await self.session.flush()

    async def list_all(self) -> list[ResearchCache]:
        """Get all cache entries."""
        stmt = select(ResearchCache)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def stats(self) -> dict:
        """Return cache statistics."""
        entries = await self.list_all()
        total_hits = sum(e.hit_count for e in entries)
        total_cost_saved = sum(e.cost_saved_usd for e in entries)
        return {
            "total_entries": len(entries),
            "total_hits": total_hits,
            "estimated_cost_saved_usd": total_cost_saved,
        }
