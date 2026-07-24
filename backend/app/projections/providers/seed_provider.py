from __future__ import annotations

from collections.abc import Iterable

from app.projections.providers.base import ProjectionProvider
from app.projections.providers.models import ProjectionPlayer
from app.projections.providers.normalization import normalize_projection_players
from app.shared.fixtures.development import (
    DEVELOPMENT_PLAYER_FIXTURES,
    DevelopmentPlayerFixture,
)


class SeedProjectionProvider(ProjectionProvider):
    def __init__(
        self,
        fixtures: Iterable[DevelopmentPlayerFixture] = DEVELOPMENT_PLAYER_FIXTURES,
    ) -> None:
        self.fixtures = tuple(fixtures)

    def load_players(self) -> list[ProjectionPlayer]:
        return normalize_projection_players(
            {
                "player_id": str(fixture.id),
                "full_name": fixture.full_name,
                "team": fixture.team,
                "primary_position": fixture.primary_position,
                "positions": ",".join(fixture.eligible_positions),
                "games": str(fixture.games),
                "minutes_per_game": str(fixture.minutes_per_game),
                "fgm": str(fixture.fgm),
                "fga": str(fixture.fga),
                "ftm": str(fixture.ftm),
                "fta": str(fixture.fta),
                "rebounds": str(fixture.rebounds),
                "assists": str(fixture.assists),
                "steals": str(fixture.steals),
                "blocks": str(fixture.blocks),
                "turnovers": str(fixture.turnovers),
                "is_active": str(fixture.is_active),
            }
            for fixture in self.fixtures
        )
