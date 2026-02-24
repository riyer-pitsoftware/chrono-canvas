"""Rename validation accuracy terminology to plausibility wording

Revision ID: 005
Revises: 004
Create Date: 2026-02-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATEGORY_RENAMES = [
    ("clothing_accuracy", "clothing_plausibility", "Clothing Plausibility"),
    ("cultural_accuracy", "cultural_plausibility", "Cultural Plausibility"),
    ("temporal_accuracy", "temporal_plausibility", "Temporal Plausibility"),
    ("artistic_style", "artistic_plausibility", "Artistic Plausibility"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for old, new, display in _CATEGORY_RENAMES:
        conn.execute(
            sa.text(
                """
                UPDATE validation_rules
                SET category = :new_category,
                    display_name = :display_name
                WHERE category = :old_category
                """
            ),
            {"new_category": new, "display_name": display, "old_category": old},
        )


def downgrade() -> None:
    _DISPLAY_DOWNGRADES = {
        "artistic_style": "Artistic Style",  # original name was "Style", not "Accuracy"
    }
    conn = op.get_bind()
    for old, new, display in _CATEGORY_RENAMES:
        old_display = _DISPLAY_DOWNGRADES.get(old, display.replace("Plausibility", "Accuracy"))
        conn.execute(
            sa.text(
                """
                UPDATE validation_rules
                SET category = :old_category,
                    display_name = :old_display
                WHERE category = :new_category
                """
            ),
            {"old_category": old, "old_display": old_display, "new_category": new},
        )
