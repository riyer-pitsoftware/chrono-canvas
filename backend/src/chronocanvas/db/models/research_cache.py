from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chronocanvas.db.base import Base, TimestampMixin, UUIDMixin

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


class ResearchCache(Base, UUIDMixin, TimestampMixin):
    """Semantic cache for research node results, keyed by pgvector embeddings."""

    __tablename__ = "research_cache"

    figure_name: Mapped[str] = mapped_column(String(500), index=True)
    time_period: Mapped[str] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(255))

    # Embedding of "{figure_name} {time_period} {region}"
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    # Cached research output
    research_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Cache hit statistics
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Cost tracking
    original_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_saved_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
