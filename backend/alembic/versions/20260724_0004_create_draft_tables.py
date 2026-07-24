"""create draft tables

Revision ID: 20260724_0004
Revises: 20260724_0003
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0004"
down_revision: Union[str, Sequence[str], None] = "20260724_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_eligibilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("position_key", sa.String(length=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position_key IN ('PG', 'SG', 'SF', 'PF', 'C')",
            name="ck_player_eligibilities_position_key",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "position_key",
            name="uq_player_eligibilities_player_position",
        ),
    )
    op.create_index(
        "ix_player_eligibilities_player_id",
        "player_eligibilities",
        ["player_id"],
    )

    op.create_table(
        "draft_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("projection_set_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("draft_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("team_count", sa.Integer(), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "league_id = 1",
            name="ck_draft_sessions_singleton_league",
        ),
        sa.CheckConstraint(
            "draft_type = 'snake'",
            name="ck_draft_sessions_type_snake",
        ),
        sa.CheckConstraint(
            "status IN ('setup', 'in_progress', 'completed')",
            name="ck_draft_sessions_status",
        ),
        sa.CheckConstraint(
            "team_count BETWEEN 2 AND 30",
            name="ck_draft_sessions_team_count",
        ),
        sa.CheckConstraint(
            "rounds > 0",
            name="ck_draft_sessions_rounds_positive",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="ck_draft_sessions_completed_at_status",
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["projection_set_id"],
            ["projection_sets.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_draft_sessions_one_noncompleted_per_league",
        "draft_sessions",
        ["league_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('setup', 'in_progress')"),
    )

    op.create_table(
        "fantasy_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_session_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("draft_position", sa.Integer(), nullable=False),
        sa.Column("is_user_team", sa.Boolean(), server_default="false", nullable=False),
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
        sa.CheckConstraint(
            "draft_position > 0",
            name="ck_fantasy_teams_position_positive",
        ),
        sa.ForeignKeyConstraint(
            ["draft_session_id"],
            ["draft_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_session_id",
            "draft_position",
            name="uq_fantasy_teams_session_position",
        ),
        sa.UniqueConstraint(
            "draft_session_id",
            "id",
            name="uq_fantasy_teams_session_id",
        ),
    )
    op.create_index(
        "ix_fantasy_teams_draft_session_id",
        "fantasy_teams",
        ["draft_session_id"],
    )
    op.create_index(
        "uq_fantasy_teams_one_user_team_per_session",
        "fantasy_teams",
        ["draft_session_id"],
        unique=True,
        postgresql_where=sa.text("is_user_team = true"),
    )

    op.create_table(
        "draft_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_session_id", sa.Integer(), nullable=False),
        sa.Column("fantasy_team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("pick_in_round", sa.Integer(), nullable=False),
        sa.Column("overall_pick", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "round_number > 0",
            name="ck_draft_picks_round_positive",
        ),
        sa.CheckConstraint(
            "pick_in_round > 0",
            name="ck_draft_picks_pick_positive",
        ),
        sa.CheckConstraint(
            "overall_pick > 0",
            name="ck_draft_picks_overall_positive",
        ),
        sa.ForeignKeyConstraint(
            ["draft_session_id"],
            ["draft_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["draft_session_id", "fantasy_team_id"],
            ["fantasy_teams.draft_session_id", "fantasy_teams.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_session_id",
            "player_id",
            name="uq_draft_picks_session_player",
        ),
        sa.UniqueConstraint(
            "draft_session_id",
            "overall_pick",
            name="uq_draft_picks_session_overall",
        ),
        sa.UniqueConstraint(
            "draft_session_id",
            "round_number",
            "pick_in_round",
            name="uq_draft_picks_session_round_pick",
        ),
    )
    op.create_index(
        "ix_draft_picks_draft_session_id",
        "draft_picks",
        ["draft_session_id"],
    )
    op.create_index("ix_draft_picks_player_id", "draft_picks", ["player_id"])

    op.execute(
        """
        CREATE FUNCTION update_draft_sessions_updated_at()
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
        CREATE TRIGGER trigger_update_draft_sessions_updated_at
        BEFORE UPDATE ON draft_sessions
        FOR EACH ROW
        EXECUTE FUNCTION update_draft_sessions_updated_at()
        """
    )
    op.execute(
        """
        CREATE FUNCTION update_fantasy_teams_updated_at()
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
        CREATE TRIGGER trigger_update_fantasy_teams_updated_at
        BEFORE UPDATE ON fantasy_teams
        FOR EACH ROW
        EXECUTE FUNCTION update_fantasy_teams_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trigger_update_fantasy_teams_updated_at ON fantasy_teams")
    op.execute("DROP FUNCTION IF EXISTS update_fantasy_teams_updated_at")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_draft_sessions_updated_at ON draft_sessions")
    op.execute("DROP FUNCTION IF EXISTS update_draft_sessions_updated_at")
    op.drop_index("ix_draft_picks_player_id", table_name="draft_picks")
    op.drop_index("ix_draft_picks_draft_session_id", table_name="draft_picks")
    op.drop_table("draft_picks")
    op.drop_index(
        "uq_fantasy_teams_one_user_team_per_session",
        table_name="fantasy_teams",
    )
    op.drop_index("ix_fantasy_teams_draft_session_id", table_name="fantasy_teams")
    op.drop_table("fantasy_teams")
    op.drop_index(
        "uq_draft_sessions_one_noncompleted_per_league",
        table_name="draft_sessions",
    )
    op.drop_table("draft_sessions")
    op.drop_index(
        "ix_player_eligibilities_player_id",
        table_name="player_eligibilities",
    )
    op.drop_table("player_eligibilities")
