from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from chronocanvas.db.base import Base, TimestampMixin, UUIDMixin


class AuditFeedback(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_feedback"

    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_requests.id", ondelete="CASCADE"),
        index=True,
    )
    step_name: Mapped[str] = mapped_column(String(100))
    comment: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(255))
