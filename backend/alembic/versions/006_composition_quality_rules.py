"""Seed composition quality validation rules

Revision ID: 006
Revises: 005
Create Date: 2026-02-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_RULES = [
    (
        "pose_plausibility",
        "Pose Plausibility",
        0.20,
        "Is the stance/gesture appropriate for the figure's role and era?",
    ),
    (
        "lighting_plausibility",
        "Lighting Plausibility",
        0.15,
        "Are light sources consistent with what was available in the era?",
    ),
    (
        "color_palette_plausibility",
        "Color Palette Plausibility",
        0.15,
        "Are the pigments and dyes historically available for this period?",
    ),
]


def upgrade() -> None:
    import uuid as _uuid

    conn = op.get_bind()
    for category, display_name, weight, description in _NEW_RULES:
        conn.execute(
            sa.text(
                "INSERT INTO validation_rules "
                "(id, category, display_name, weight, description, enabled) "
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


def downgrade() -> None:
    conn = op.get_bind()
    for category, _, _, _ in _NEW_RULES:
        conn.execute(
            sa.text("DELETE FROM validation_rules WHERE category = :category"),
            {"category": category},
        )
