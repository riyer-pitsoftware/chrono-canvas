"""Add audit trail fields

Revision ID: 002
Revises: 001
Create Date: 2026-02-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generation_requests",
        sa.Column("llm_calls", postgresql.JSONB, server_default="[]"),
    )
    op.add_column(
        "validation_results",
        sa.Column("reasoning", sa.Text),
    )


def downgrade() -> None:
    op.drop_column("validation_results", "reasoning")
    op.drop_column("generation_requests", "llm_calls")
