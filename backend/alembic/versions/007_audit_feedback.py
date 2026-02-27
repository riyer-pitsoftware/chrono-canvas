"""Audit feedback table for educator annotations on pipeline steps

Revision ID: 007
Revises: 006
Create Date: 2026-02-26

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_feedback",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_feedback")
