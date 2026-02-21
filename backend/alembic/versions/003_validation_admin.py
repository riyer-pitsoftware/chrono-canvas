"""Validation admin: rules table, admin_settings, human review fields

Revision ID: 003
Revises: 002
Create Date: 2026-02-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_RULES = [
    ("clothing_accuracy", "Clothing Accuracy", 0.25, "Are the clothes period-appropriate?"),
    ("cultural_accuracy", "Cultural Accuracy", 0.25, "Are cultural elements correct?"),
    ("temporal_accuracy", "Temporal Accuracy", 0.25, "Are there anachronistic elements?"),
    ("artistic_style", "Artistic Style", 0.25, "Does the art style match the period?"),
]


def upgrade() -> None:
    op.create_table(
        "validation_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0.25"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "admin_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )

    op.add_column(
        "generation_requests",
        sa.Column("human_review_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "generation_requests",
        sa.Column("human_review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "generation_requests",
        sa.Column("human_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Seed default validation rules
    conn = op.get_bind()
    import uuid as _uuid
    for category, display_name, weight, description in _DEFAULT_RULES:
        conn.execute(
            sa.text(
                "INSERT INTO validation_rules (id, category, display_name, weight, description, enabled) "
                "VALUES (:id, :category, :display_name, :weight, :description, true)"
            ),
            {
                "id": str(_uuid.uuid4()),
                "category": category,
                "display_name": display_name,
                "weight": weight,
                "description": description,
            },
        )

    # Seed default pass threshold
    conn.execute(
        sa.text("INSERT INTO admin_settings (key, value) VALUES (:key, :value)"),
        {"key": "validation_pass_threshold", "value": "70.0"},
    )


def downgrade() -> None:
    op.drop_column("generation_requests", "human_reviewed_at")
    op.drop_column("generation_requests", "human_review_notes")
    op.drop_column("generation_requests", "human_review_status")
    op.drop_table("admin_settings")
    op.drop_table("validation_rules")
