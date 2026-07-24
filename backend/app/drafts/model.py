from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.players.model import Player
from app.shared.database.base import Base


class DraftSession(Base):
    __tablename__ = "draft_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="RESTRICT"), nullable=False
    )
    projection_set_id: Mapped[int] = mapped_column(
        ForeignKey("projection_sets.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    draft_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    team_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    teams: Mapped[list["FantasyTeam"]] = relationship(
        back_populates="draft_session",
        cascade="all, delete-orphan",
        order_by="FantasyTeam.draft_position",
    )
    picks: Mapped[list["DraftPick"]] = relationship(
        back_populates="draft_session",
        cascade="all, delete-orphan",
        order_by="DraftPick.overall_pick",
        overlaps="fantasy_team,picks",
    )

    __table_args__ = (
        CheckConstraint("league_id = 1", name="ck_draft_sessions_singleton_league"),
        CheckConstraint("draft_type = 'snake'", name="ck_draft_sessions_type_snake"),
        CheckConstraint(
            "status IN ('setup', 'in_progress', 'completed')",
            name="ck_draft_sessions_status",
        ),
        CheckConstraint("team_count BETWEEN 2 AND 30", name="ck_draft_sessions_team_count"),
        CheckConstraint("rounds > 0", name="ck_draft_sessions_rounds_positive"),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="ck_draft_sessions_completed_at_status",
        ),
        Index(
            "uq_draft_sessions_one_noncompleted_per_league",
            "league_id",
            unique=True,
            postgresql_where=text("status IN ('setup', 'in_progress')"),
        ),
    )


class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_session_id: Mapped[int] = mapped_column(
        ForeignKey("draft_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    draft_position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_user_team: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    draft_session: Mapped[DraftSession] = relationship(back_populates="teams")
    picks: Mapped[list["DraftPick"]] = relationship(
        back_populates="fantasy_team",
        overlaps="draft_session,picks",
    )

    __table_args__ = (
        UniqueConstraint(
            "draft_session_id",
            "draft_position",
            name="uq_fantasy_teams_session_position",
        ),
        UniqueConstraint(
            "draft_session_id",
            "id",
            name="uq_fantasy_teams_session_id",
        ),
        CheckConstraint("draft_position > 0", name="ck_fantasy_teams_position_positive"),
        Index(
            "uq_fantasy_teams_one_user_team_per_session",
            "draft_session_id",
            unique=True,
            postgresql_where=text("is_user_team = true"),
        ),
    )


class DraftPick(Base):
    __tablename__ = "draft_picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_session_id: Mapped[int] = mapped_column(
        ForeignKey("draft_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fantasy_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pick_in_round: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_pick: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    draft_session: Mapped[DraftSession] = relationship(
        back_populates="picks",
        overlaps="fantasy_team,picks",
    )
    fantasy_team: Mapped[FantasyTeam] = relationship(
        back_populates="picks",
        overlaps="draft_session,picks",
    )
    player: Mapped[Player] = relationship()

    __table_args__ = (
        ForeignKeyConstraint(
            ["draft_session_id", "fantasy_team_id"],
            ["fantasy_teams.draft_session_id", "fantasy_teams.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "draft_session_id",
            "player_id",
            name="uq_draft_picks_session_player",
        ),
        UniqueConstraint(
            "draft_session_id",
            "overall_pick",
            name="uq_draft_picks_session_overall",
        ),
        UniqueConstraint(
            "draft_session_id",
            "round_number",
            "pick_in_round",
            name="uq_draft_picks_session_round_pick",
        ),
        CheckConstraint("round_number > 0", name="ck_draft_picks_round_positive"),
        CheckConstraint("pick_in_round > 0", name="ck_draft_picks_pick_positive"),
        CheckConstraint("overall_pick > 0", name="ck_draft_picks_overall_positive"),
    )
