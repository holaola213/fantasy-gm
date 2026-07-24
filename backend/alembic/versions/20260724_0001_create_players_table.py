"""create players table

Revision ID: 20260724_0001
Revises:
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("team", sa.String(length=10), nullable=True),
        sa.Column("primary_position", sa.String(length=10), nullable=True),
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
    )
    op.create_index("ix_players_full_name", "players", ["full_name"])
    op.create_index("ix_players_is_active", "players", ["is_active"])
    op.create_index("ix_players_primary_position", "players", ["primary_position"])
    op.create_index("ix_players_team", "players", ["team"])
    op.execute(
        """
        CREATE FUNCTION update_players_updated_at()
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
        CREATE TRIGGER trigger_update_players_updated_at
        BEFORE UPDATE ON players
        FOR EACH ROW
        EXECUTE FUNCTION update_players_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trigger_update_players_updated_at ON players")
    op.execute("DROP FUNCTION IF EXISTS update_players_updated_at")
    op.drop_index("ix_players_team", table_name="players")
    op.drop_index("ix_players_primary_position", table_name="players")
    op.drop_index("ix_players_is_active", table_name="players")
    op.drop_index("ix_players_full_name", table_name="players")
    op.drop_table("players")
