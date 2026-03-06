"""Add Neo-Mumbai-Noir tables (stories, characters, scenes, images, face_swaps)

Revision ID: 009
Revises: 008
Create Date: 2026-03-05

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "neo_stories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "neo_characters",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_stories.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("slug", sa.String(255), nullable=False, index=True),
        sa.Column("age", sa.String(100), nullable=True),
        sa.Column("ethnicity", sa.String(255), nullable=True),
        sa.Column("gender", sa.String(100), nullable=True),
        sa.Column("facial_features", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("clothing", sa.Text(), nullable=True),
        sa.Column("key_scenes", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("emotions", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("story_id", "slug", name="uq_neo_characters_story_slug"),
    )

    op.create_table(
        "neo_scenes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "character_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_characters.id"),
            nullable=False,
        ),
        sa.Column("scene_key", sa.String(255), nullable=False),
        sa.Column("scene_name", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("character_id", "scene_key", name="uq_neo_scenes_character_key"),
    )

    op.create_table(
        "neo_images",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "character_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_characters.id"),
            nullable=True,
        ),
        sa.Column(
            "scene_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_scenes.id"),
            nullable=True,
        ),
        sa.Column("image_type", sa.String(100), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False, unique=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("photographer", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "neo_face_swaps",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_image_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_images.id"),
            nullable=False,
        ),
        sa.Column(
            "target_image_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_images.id"),
            nullable=False,
        ),
        sa.Column(
            "result_image_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("neo_images.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("neo_face_swaps")
    op.drop_table("neo_images")
    op.drop_table("neo_scenes")
    op.drop_table("neo_characters")
    op.drop_table("neo_stories")
