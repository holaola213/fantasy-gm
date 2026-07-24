from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    team: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    primary_position: Mapped[str | None] = mapped_column(
        String(10), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
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

    eligibilities: Mapped[list["PlayerEligibility"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        order_by="PlayerEligibility.position_key",
    )


class PlayerEligibility(Base):
    __tablename__ = "player_eligibilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_key: Mapped[str] = mapped_column(String(2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    player: Mapped[Player] = relationship(back_populates="eligibilities")

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "position_key",
            name="uq_player_eligibilities_player_position",
        ),
        CheckConstraint(
            "position_key IN ('PG', 'SG', 'SF', 'PF', 'C')",
            name="ck_player_eligibilities_position_key",
        ),
    )
