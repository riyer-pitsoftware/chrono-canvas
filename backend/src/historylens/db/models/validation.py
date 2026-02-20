import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from historylens.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from historylens.db.models.request import GenerationRequest


class ValidationResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_results"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_requests.id")
    )
    category: Mapped[str] = mapped_column(String(100))
    rule_name: Mapped[str] = mapped_column(String(255))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[str | None] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text)
    suggestions: Mapped[dict | None] = mapped_column(JSONB, default=list)

    request: Mapped["GenerationRequest"] = relationship(back_populates="validations")
