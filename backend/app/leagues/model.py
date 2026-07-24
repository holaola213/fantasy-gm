from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team_count: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_format: Mapped[str] = mapped_column(String(20), nullable=False)
    acquisition_limit_per_day: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    playoff_team_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    scoring_rules: Mapped[list["ScoringRule"]] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
        order_by="ScoringRule.sort_order",
    )
    roster_slots: Mapped[list["RosterSlot"]] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
        order_by="RosterSlot.sort_order",
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_leagues_singleton_id"),
        CheckConstraint("platform = 'ESPN'", name="ck_leagues_platform_espn"),
        CheckConstraint(
            "scoring_format = 'points'", name="ck_leagues_scoring_format_points"
        ),
        CheckConstraint("team_count BETWEEN 2 AND 30", name="ck_leagues_team_count"),
        CheckConstraint(
            "playoff_team_count >= 2 AND playoff_team_count <= team_count",
            name="ck_leagues_playoff_team_count",
        ),
        CheckConstraint(
            "season BETWEEN 2000 AND 2100",
            name="ck_leagues_reasonable_season",
        ),
        CheckConstraint(
            "acquisition_limit_per_day IS NULL OR "
            "(acquisition_limit_per_day >= 0 AND acquisition_limit_per_day <= 100)",
            name="ck_leagues_acquisition_limit_per_day",
        ),
    )


class ScoringRule(Base):
    __tablename__ = "scoring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stat_key: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    points: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    league: Mapped[League] = relationship(back_populates="scoring_rules")

    __table_args__ = (
        UniqueConstraint("league_id", "stat_key", name="uq_scoring_rules_league_key"),
    )


class RosterSlot(Base):
    __tablename__ = "roster_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_key: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    league: Mapped[League] = relationship(back_populates="roster_slots")

    __table_args__ = (
        UniqueConstraint("league_id", "slot_key", name="uq_roster_slots_league_key"),
        CheckConstraint("count >= 0", name="ck_roster_slots_count_nonnegative"),
    )
