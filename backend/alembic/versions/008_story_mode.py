"""Add run_type and storyboard_data columns for story mode

Revision ID: 008
Revises: 007
Create Date: 2026-02-28

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generation_requests",
        sa.Column("run_type", sa.String(50), server_default="portrait", nullable=False),
    )
    op.add_column(
        "generation_requests",
        sa.Column("storyboard_data", sa.dialects.postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_requests", "storyboard_data")
    op.drop_column("generation_requests", "run_type")
