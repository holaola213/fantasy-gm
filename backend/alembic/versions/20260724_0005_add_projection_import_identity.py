"""add projection import identity

Revision ID: 20260724_0005
Revises: 20260724_0004
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0005"
down_revision: Union[str, Sequence[str], None] = "20260724_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_projection_sets_source_season_type_as_of",
        "projection_sets",
        type_="unique",
    )
    op.create_index(
        "uq_projection_sets_one_active_per_source_season_type",
        "projection_sets",
        ["source_id", "season", "projection_type"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "player_source_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_player_id", sa.String(length=120), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["projection_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "source_player_id",
            name="uq_player_source_identities_source_player",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate_count = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT source_id, season, projection_type, as_of_date
                FROM projection_sets
                GROUP BY source_id, season, projection_type, as_of_date
                HAVING count(*) > 1
            ) duplicates
            """
        )
    )
    if duplicate_count:
        raise RuntimeError(
            "Downgrade to 20260724_0004 is unsupported while duplicate "
            "projection snapshots exist for the same source, season, type, "
            "and as-of date. Remove or archive duplicate snapshots manually "
            "before downgrading."
        )
    op.drop_index(
        "uq_projection_sets_one_active_per_source_season_type",
        table_name="projection_sets",
    )
    op.drop_table("player_source_identities")
    op.create_unique_constraint(
        "uq_projection_sets_source_season_type_as_of",
        "projection_sets",
        ["source_id", "season", "projection_type", "as_of_date"],
    )
