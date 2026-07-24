from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProjectionPlayer:
    source_player_id: str
    full_name: str
    team: str | None
    primary_position: str | None
    positions: tuple[str, ...]
    games: Decimal
    minutes_per_game: Decimal
    fgm: Decimal
    fga: Decimal
    ftm: Decimal
    fta: Decimal
    rebounds: Decimal
    assists: Decimal
    steals: Decimal
    blocks: Decimal
    turnovers: Decimal
    is_active: bool = True
