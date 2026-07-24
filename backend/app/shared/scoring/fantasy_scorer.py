from decimal import Decimal
from typing import Iterable, Protocol

from app.projections.model import PlayerProjection


class ScoringRuleLike(Protocol):
    stat_key: str
    points: Decimal


STAT_TO_SCORING_KEY = {
    "fgm": "FGM",
    "fga": "FGA",
    "ftm": "FTM",
    "fta": "FTA",
    "rebounds": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TO",
}


class FantasyScorer:
    def __init__(self, scoring_rules: Iterable[ScoringRuleLike]) -> None:
        self.scoring_rules = {rule.stat_key: rule.points for rule in scoring_rules}

    def fantasy_points_per_game(self, projection: PlayerProjection) -> Decimal:
        total = Decimal("0")
        for stat_name, scoring_key in STAT_TO_SCORING_KEY.items():
            stat_value = getattr(projection, stat_name)
            scoring_value = self.scoring_rules.get(scoring_key, Decimal("0"))
            total += stat_value * scoring_value
        return total

    def projected_fantasy_points(self, projection: PlayerProjection) -> Decimal:
        return self.fantasy_points_per_game(projection) * projection.games
