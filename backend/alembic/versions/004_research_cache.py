"""Add research cache table with pgvector

Revision ID: 004
Revises: 003
Create Date: 2026-02-21

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.execute(
        sa.text("""
        CREATE TABLE research_cache (
            id UUID PRIMARY KEY,
            figure_name VARCHAR(500) NOT NULL,
            time_period VARCHAR(255) NOT NULL,
            region VARCHAR(255) NOT NULL,
            embedding VECTOR(384) NOT NULL,
            research_data JSONB NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0,
            last_accessed_at TIMESTAMP WITH TIME ZONE,
            original_cost_usd FLOAT NOT NULL DEFAULT 0.0,
            cost_saved_usd FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """)
    )
    index_sql = "CREATE INDEX research_cache_figure_name_idx ON research_cache(figure_name)"
    conn.execute(sa.text(index_sql))


def downgrade() -> None:
    op.drop_table("research_cache")
