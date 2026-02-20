"""Initial migration

Revision ID: 001
Revises:
Create Date: 2026-02-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("start_year", sa.Integer, nullable=False),
        sa.Column("end_year", sa.Integer, nullable=False),
        sa.Column("region", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("clothing_styles", postgresql.JSONB),
        sa.Column("art_references", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "figures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("birth_year", sa.Integer),
        sa.Column("death_year", sa.Integer),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("periods.id")),
        sa.Column("nationality", sa.String(100)),
        sa.Column("occupation", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("physical_description", sa.Text),
        sa.Column("clothing_notes", sa.Text),
        sa.Column("metadata_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "generation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("figure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("figures.id")),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("current_agent", sa.String(100)),
        sa.Column("extracted_data", postgresql.JSONB),
        sa.Column("research_data", postgresql.JSONB),
        sa.Column("generated_prompt", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("agent_trace", postgresql.JSONB),
        sa.Column("llm_costs", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "generated_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_requests.id"),
            nullable=False,
        ),
        sa.Column("figure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("figures.id")),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("thumbnail_path", sa.String(500)),
        sa.Column("prompt_used", sa.String(2000)),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("width", sa.Integer, default=512),
        sa.Column("height", sa.Integer, default=512),
        sa.Column("validation_score", sa.Float),
        sa.Column("generation_params", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generation_requests.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("rule_name", sa.String(255), nullable=False),
        sa.Column("passed", sa.Boolean, default=False),
        sa.Column("score", sa.Float, default=0.0),
        sa.Column("details", sa.Text),
        sa.Column("suggestions", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("details", sa.Text),
        sa.Column("metadata_json", postgresql.JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("validation_results")
    op.drop_table("generated_images")
    op.drop_table("generation_requests")
    op.drop_table("figures")
    op.drop_table("periods")
