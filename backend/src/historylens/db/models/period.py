from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from historylens.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from historylens.db.models.figure import Figure


class Period(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "periods"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    start_year: Mapped[int] = mapped_column(Integer)
    end_year: Mapped[int] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    clothing_styles: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    art_references: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    figures: Mapped[list["Figure"]] = relationship(back_populates="period")
