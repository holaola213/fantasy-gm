from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


DEFAULT_PROJECTED_GAMES = Decimal("68")
DEFAULT_MINUTES_PER_GAME = Decimal("26")


@dataclass(frozen=True)
class PlayerBootstrapOverride:
    projected_games: Decimal | None = None
    minutes_per_game: Decimal | None = None


@dataclass(frozen=True)
class BootstrapAssumptions:
    default_projected_games: Decimal = DEFAULT_PROJECTED_GAMES
    default_minutes_per_game: Decimal = DEFAULT_MINUTES_PER_GAME
    player_overrides: dict[str, PlayerBootstrapOverride] = field(default_factory=dict)

    def projected_games_for(self, source_player_id: str) -> Decimal:
        override = self.player_overrides.get(source_player_id)
        if override and override.projected_games is not None:
            return override.projected_games
        return self.default_projected_games

    def minutes_per_game_for(self, source_player_id: str) -> Decimal:
        override = self.player_overrides.get(source_player_id)
        if override and override.minutes_per_game is not None:
            return override.minutes_per_game
        return self.default_minutes_per_game

    def uses_default_assumptions(self, source_player_id: str) -> bool:
        override = self.player_overrides.get(source_player_id)
        return override is None or (
            override.projected_games is None and override.minutes_per_game is None
        )
