import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from historylens.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from historylens.db.models.image import GeneratedImage
    from historylens.db.models.period import Period
    from historylens.db.models.request import GenerationRequest


class Figure(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "figures"

    name: Mapped[str] = mapped_column(String(255), index=True)
    birth_year: Mapped[int | None]
    death_year: Mapped[int | None]
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("periods.id")
    )
    nationality: Mapped[str | None] = mapped_column(String(100))
    occupation: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    physical_description: Mapped[str | None] = mapped_column(Text)
    clothing_notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    period: Mapped["Period | None"] = relationship(back_populates="figures")
    requests: Mapped[list["GenerationRequest"]] = relationship(back_populates="figure")
    images: Mapped[list["GeneratedImage"]] = relationship(back_populates="figure")
