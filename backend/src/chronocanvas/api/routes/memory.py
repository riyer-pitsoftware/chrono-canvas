from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.memory import (
    CacheEntryResponse,
    CacheListResponse,
    CacheStatsResponse,
)
from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.research_cache import ResearchCacheRepository
from chronocanvas.memory.cache_service import ResearchCacheService

router = APIRouter(prefix="/memory", tags=["memory"])
_cache_service = ResearchCacheService()


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get cache statistics: total entries, hits, and estimated cost saved."""
    return await _cache_service.stats()


@router.get("/entries", response_model=CacheListResponse)
async def list_cache_entries(session: AsyncSession = Depends(get_session)):
    """List all cached research entries."""
    stats = await _cache_service.stats()

    repo = ResearchCacheRepository(session)
    entries = await repo.list_all()

    cache_entries = [
        CacheEntryResponse(
            id=str(entry.id),
            figure_name=entry.figure_name,
            time_period=entry.time_period,
            region=entry.region,
            hit_count=entry.hit_count,
            cost_saved_usd=entry.cost_saved_usd,
            original_cost_usd=entry.original_cost_usd,
        )
        for entry in entries
    ]

    return CacheListResponse(entries=cache_entries, stats=stats)


@router.delete("/entries")
async def clear_cache(session: AsyncSession = Depends(get_session)):
    """Clear all cached research entries."""
    count = await _cache_service.clear_all()
    return {"deleted_count": count}
