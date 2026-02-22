from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from chronocanvas.db.base import Base, TimestampMixin, UUIDMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45))
