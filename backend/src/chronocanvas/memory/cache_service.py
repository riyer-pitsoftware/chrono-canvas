import logging
import uuid
from datetime import datetime, timezone

from chronocanvas.db.engine import async_session
from chronocanvas.db.models.research_cache import ResearchCache
from chronocanvas.db.repositories.research_cache import ResearchCacheRepository
from chronocanvas.memory.embedder import embed_text

logger = logging.getLogger(__name__)


class ResearchCacheService:
    """Service for semantic caching of research results."""

    async def lookup(
        self, figure_name: str, time_period: str, region: str, threshold: float = 0.85
    ) -> dict | None:
        """Lookup research result in cache."""
        text = f"{figure_name} {time_period} {region}"
        embedding = await embed_text(text)

        async with async_session() as session:
            repo = ResearchCacheRepository(session)
            entry = await repo.find_similar(embedding, threshold)
            if entry:
                logger.info(
                    f"Cache hit for {figure_name} ({time_period}), "
                    f"saving ${entry.original_cost_usd:.4f}"
                )
                await repo.record_hit(entry.id, entry.original_cost_usd)
                await session.commit()
                return entry.research_data
        return None

    async def store(
        self,
        figure_name: str,
        time_period: str,
        region: str,
        research_data: dict,
        cost_usd: float,
    ) -> None:
        """Store research result in cache."""
        text = f"{figure_name} {time_period} {region}"
        embedding = await embed_text(text)

        async with async_session() as session:
            cache_entry = ResearchCache(
                id=uuid.uuid4(),
                figure_name=figure_name,
                time_period=time_period,
                region=region,
                embedding=embedding,
                research_data=research_data,
                hit_count=0,
                last_accessed_at=datetime.now(timezone.utc),
                original_cost_usd=cost_usd,
                cost_saved_usd=0.0,
            )
            session.add(cache_entry)
            await session.flush()
            logger.info(f"Cached research for {figure_name} ({time_period}), cost: ${cost_usd:.4f}")
            await session.commit()

    async def stats(self) -> dict:
        """Get cache statistics."""
        async with async_session() as session:
            repo = ResearchCacheRepository(session)
            return await repo.stats()

    async def clear_all(self) -> int:
        """Clear all cache entries."""
        async with async_session() as session:
            from sqlalchemy import delete

            result = await session.execute(delete(ResearchCache))
            await session.commit()
            return result.rowcount
