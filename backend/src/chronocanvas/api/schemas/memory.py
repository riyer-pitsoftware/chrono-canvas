from pydantic import BaseModel


class CacheEntryResponse(BaseModel):
    id: str
    figure_name: str
    time_period: str
    region: str
    hit_count: int
    cost_saved_usd: float
    original_cost_usd: float


class CacheStatsResponse(BaseModel):
    total_entries: int
    total_hits: int
    estimated_cost_saved_usd: float


class CacheListResponse(BaseModel):
    entries: list[CacheEntryResponse]
    stats: CacheStatsResponse
