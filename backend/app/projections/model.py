from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.players.model import Player
from app.shared.database.base import Base


class ProjectionSource(Base):
    __tablename__ = "projection_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
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

    projection_sets: Mapped[list["ProjectionSet"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("key", name="uq_projection_sources_key"),
    )


class ProjectionSet(Base):
    __tablename__ = "projection_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("projection_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_type: Mapped[str] = mapped_column(String(40), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    source: Mapped[ProjectionSource] = relationship(back_populates="projection_sets")
    player_projections: Mapped[list["PlayerProjection"]] = relationship(
        back_populates="projection_set",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "season BETWEEN 2000 AND 2100",
            name="ck_projection_sets_reasonable_season",
        ),
        CheckConstraint(
            "projection_type = 'season'",
            name="ck_projection_sets_projection_type_season",
        ),
        Index(
            "uq_projection_sets_one_active_per_source_season_type",
            "source_id",
            "season",
            "projection_type",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )


class PlayerSourceIdentity(Base):
    __tablename__ = "player_source_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("projection_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_player_id: Mapped[str] = mapped_column(String(120), nullable=False)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
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

    source: Mapped[ProjectionSource] = relationship()
    player: Mapped[Player] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "source_player_id",
            name="uq_player_source_identities_source_player",
        ),
    )


class PlayerProjection(Base):
    __tablename__ = "player_projections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projection_set_id: Mapped[int] = mapped_column(
        ForeignKey("projection_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    games: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    minutes_per_game: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    fgm: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    fga: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    ftm: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    fta: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    rebounds: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    assists: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    steals: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    blocks: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    turnovers: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    points: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    projection_set: Mapped[ProjectionSet] = relationship(
        back_populates="player_projections"
    )
    player: Mapped[Player] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "projection_set_id",
            "player_id",
            name="uq_player_projections_set_player",
        ),
        CheckConstraint("games >= 0 AND games <= 82", name="ck_player_projections_games"),
        CheckConstraint(
            "minutes_per_game >= 0 AND minutes_per_game <= 60",
            name="ck_player_projections_minutes_per_game",
        ),
        CheckConstraint("fgm >= 0", name="ck_player_projections_fgm_nonnegative"),
        CheckConstraint("fga >= 0", name="ck_player_projections_fga_nonnegative"),
        CheckConstraint("ftm >= 0", name="ck_player_projections_ftm_nonnegative"),
        CheckConstraint("fta >= 0", name="ck_player_projections_fta_nonnegative"),
        CheckConstraint(
            "rebounds >= 0", name="ck_player_projections_rebounds_nonnegative"
        ),
        CheckConstraint("assists >= 0", name="ck_player_projections_assists_nonnegative"),
        CheckConstraint("steals >= 0", name="ck_player_projections_steals_nonnegative"),
        CheckConstraint("blocks >= 0", name="ck_player_projections_blocks_nonnegative"),
        CheckConstraint(
            "turnovers >= 0", name="ck_player_projections_turnovers_nonnegative"
        ),
        CheckConstraint(
            "points IS NULL OR points >= 0",
            name="ck_player_projections_points_nonnegative",
        ),
        CheckConstraint("fgm <= fga", name="ck_player_projections_fgm_lte_fga"),
        CheckConstraint("ftm <= fta", name="ck_player_projections_ftm_lte_fta"),
    )
