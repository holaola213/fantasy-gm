"""create projection tables

Revision ID: 20260724_0003
Revises: 20260724_0002
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0003"
down_revision: Union[str, Sequence[str], None] = "20260724_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projection_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_projection_sources_key"),
    )
    op.create_table(
        "projection_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("projection_type", sa.String(length=40), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "projection_type = 'season'",
            name="ck_projection_sets_projection_type_season",
        ),
        sa.CheckConstraint(
            "season BETWEEN 2000 AND 2100",
            name="ck_projection_sets_reasonable_season",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["projection_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "season",
            "projection_type",
            "as_of_date",
            name="uq_projection_sets_source_season_type_as_of",
        ),
    )
    op.create_index(
        "uq_projection_sets_one_active_per_source_season_type",
        "projection_sets",
        ["source_id", "season", "projection_type"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "player_projections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("projection_set_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("games", sa.Numeric(5, 2), nullable=False),
        sa.Column("minutes_per_game", sa.Numeric(5, 2), nullable=False),
        sa.Column("fgm", sa.Numeric(6, 3), nullable=False),
        sa.Column("fga", sa.Numeric(6, 3), nullable=False),
        sa.Column("ftm", sa.Numeric(6, 3), nullable=False),
        sa.Column("fta", sa.Numeric(6, 3), nullable=False),
        sa.Column("rebounds", sa.Numeric(6, 3), nullable=False),
        sa.Column("assists", sa.Numeric(6, 3), nullable=False),
        sa.Column("steals", sa.Numeric(6, 3), nullable=False),
        sa.Column("blocks", sa.Numeric(6, 3), nullable=False),
        sa.Column("turnovers", sa.Numeric(6, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "games >= 0 AND games <= 82", name="ck_player_projections_games"
        ),
        sa.CheckConstraint(
            "minutes_per_game >= 0 AND minutes_per_game <= 60",
            name="ck_player_projections_minutes_per_game",
        ),
        sa.CheckConstraint("fgm >= 0", name="ck_player_projections_fgm_nonnegative"),
        sa.CheckConstraint("fga >= 0", name="ck_player_projections_fga_nonnegative"),
        sa.CheckConstraint("ftm >= 0", name="ck_player_projections_ftm_nonnegative"),
        sa.CheckConstraint("fta >= 0", name="ck_player_projections_fta_nonnegative"),
        sa.CheckConstraint(
            "rebounds >= 0", name="ck_player_projections_rebounds_nonnegative"
        ),
        sa.CheckConstraint(
            "assists >= 0", name="ck_player_projections_assists_nonnegative"
        ),
        sa.CheckConstraint(
            "steals >= 0", name="ck_player_projections_steals_nonnegative"
        ),
        sa.CheckConstraint(
            "blocks >= 0", name="ck_player_projections_blocks_nonnegative"
        ),
        sa.CheckConstraint(
            "turnovers >= 0", name="ck_player_projections_turnovers_nonnegative"
        ),
        sa.CheckConstraint("fgm <= fga", name="ck_player_projections_fgm_lte_fga"),
        sa.CheckConstraint("ftm <= fta", name="ck_player_projections_ftm_lte_fta"),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["projection_set_id"], ["projection_sets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "projection_set_id",
            "player_id",
            name="uq_player_projections_set_player",
        ),
    )
    op.create_index(
        "ix_player_projections_player_id", "player_projections", ["player_id"]
    )
    op.execute(
        """
        CREATE FUNCTION update_projection_sources_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trigger_update_projection_sources_updated_at
        BEFORE UPDATE ON projection_sources
        FOR EACH ROW
        EXECUTE FUNCTION update_projection_sources_updated_at()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trigger_update_projection_sources_updated_at "
        "ON projection_sources"
    )
    op.execute("DROP FUNCTION IF EXISTS update_projection_sources_updated_at")
    op.drop_index("ix_player_projections_player_id", table_name="player_projections")
    op.drop_table("player_projections")
    op.drop_index(
        "uq_projection_sets_one_active_per_source_season_type",
        table_name="projection_sets",
    )
    op.drop_table("projection_sets")
    op.drop_table("projection_sources")
