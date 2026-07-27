"""Add projected points to projection rows.

Revision ID: 20260724_0006
Revises: 20260724_0005
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260724_0006"
down_revision: str | None = "20260724_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "player_projections",
        sa.Column("points", sa.Numeric(6, 3), nullable=True),
    )
    op.create_check_constraint(
        "ck_player_projections_points_nonnegative",
        "player_projections",
        "points IS NULL OR points >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_player_projections_points_nonnegative",
        "player_projections",
        type_="check",
    )
    op.drop_column("player_projections", "points")
