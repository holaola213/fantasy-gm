"""create league configuration tables

Revision ID: 20260724_0002
Revises: 20260724_0001
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0002"
down_revision: Union[str, Sequence[str], None] = "20260724_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_count", sa.Integer(), nullable=False),
        sa.Column("scoring_format", sa.String(length=20), nullable=False),
        sa.Column("acquisition_limit_per_day", sa.Integer(), nullable=True),
        sa.Column("playoff_team_count", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("id = 1", name="ck_leagues_singleton_id"),
        sa.CheckConstraint("platform = 'ESPN'", name="ck_leagues_platform_espn"),
        sa.CheckConstraint(
            "scoring_format = 'points'", name="ck_leagues_scoring_format_points"
        ),
        sa.CheckConstraint(
            "team_count BETWEEN 2 AND 30", name="ck_leagues_team_count"
        ),
        sa.CheckConstraint(
            "playoff_team_count >= 2 AND playoff_team_count <= team_count",
            name="ck_leagues_playoff_team_count",
        ),
        sa.CheckConstraint(
            "season BETWEEN 2000 AND 2100", name="ck_leagues_reasonable_season"
        ),
        sa.CheckConstraint(
            "acquisition_limit_per_day IS NULL OR "
            "(acquisition_limit_per_day >= 0 AND acquisition_limit_per_day <= 100)",
            name="ck_leagues_acquisition_limit_per_day",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scoring_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("stat_key", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("points", sa.Numeric(10, 4), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "league_id", "stat_key", name="uq_scoring_rules_league_key"
        ),
    )
    op.create_index(
        "ix_scoring_rules_league_id", "scoring_rules", ["league_id"]
    )
    op.create_table(
        "roster_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("slot_key", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("count >= 0", name="ck_roster_slots_count_nonnegative"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "slot_key", name="uq_roster_slots_league_key"),
    )
    op.create_index("ix_roster_slots_league_id", "roster_slots", ["league_id"])
    op.execute(
        """
        CREATE FUNCTION update_leagues_updated_at()
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
        CREATE TRIGGER trigger_update_leagues_updated_at
        BEFORE UPDATE ON leagues
        FOR EACH ROW
        EXECUTE FUNCTION update_leagues_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trigger_update_leagues_updated_at ON leagues")
    op.execute("DROP FUNCTION IF EXISTS update_leagues_updated_at")
    op.drop_index("ix_roster_slots_league_id", table_name="roster_slots")
    op.drop_table("roster_slots")
    op.drop_index("ix_scoring_rules_league_id", table_name="scoring_rules")
    op.drop_table("scoring_rules")
    op.drop_table("leagues")
