import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from historylens.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from historylens.db.models.figure import Figure
    from historylens.db.models.image import GeneratedImage
    from historylens.db.models.validation import ValidationResult


class RequestStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    RESEARCHING = "researching"
    GENERATING_PROMPT = "generating_prompt"
    GENERATING_IMAGE = "generating_image"
    VALIDATING = "validating"
    SWAPPING_FACE = "swapping_face"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "generation_requests"

    figure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("figures.id")
    )
    input_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default=RequestStatus.PENDING, index=True)
    current_agent: Mapped[str | None] = mapped_column(String(100))
    extracted_data: Mapped[dict | None] = mapped_column(JSONB)
    research_data: Mapped[dict | None] = mapped_column(JSONB)
    generated_prompt: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    agent_trace: Mapped[dict | None] = mapped_column(JSONB, default=list)
    llm_costs: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    llm_calls: Mapped[dict | None] = mapped_column(JSONB, default=list)

    figure: Mapped["Figure | None"] = relationship(back_populates="requests")
    images: Mapped[list["GeneratedImage"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    validations: Mapped[list["ValidationResult"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
