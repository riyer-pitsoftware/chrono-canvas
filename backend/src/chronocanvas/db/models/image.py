import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chronocanvas.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from chronocanvas.db.models.figure import Figure
    from chronocanvas.db.models.request import GenerationRequest


class GeneratedImage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "generated_images"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_requests.id")
    )
    figure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("figures.id")
    )
    file_path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    prompt_used: Mapped[str | None] = mapped_column(String(2000))
    provider: Mapped[str] = mapped_column(String(50))
    width: Mapped[int] = mapped_column(Integer, default=512)
    height: Mapped[int] = mapped_column(Integer, default=512)
    validation_score: Mapped[float | None] = mapped_column(Float)
    generation_params: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    request: Mapped["GenerationRequest"] = relationship(back_populates="images")
    figure: Mapped["Figure | None"] = relationship(back_populates="images")
