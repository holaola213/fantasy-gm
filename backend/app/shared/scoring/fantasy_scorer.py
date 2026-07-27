from decimal import Decimal
from dataclasses import dataclass
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
    "turnovers": "TOV",
    "points": "PTS",
}

SCORING_KEY_ALIASES = {
    "TOV": ("TOV", "TO"),
}


@dataclass(frozen=True)
class ScoringContribution:
    stat_name: str
    scoring_key: str
    configured_stat_key: str | None
    projection_value: Decimal | None
    applied_projection_value: Decimal
    league_weight: Decimal
    contribution: Decimal


@dataclass(frozen=True)
class UnsupportedScoringRule:
    stat_key: str
    points: Decimal
    message: str


class FantasyScorer:
    def __init__(self, scoring_rules: Iterable[ScoringRuleLike]) -> None:
        self.scoring_rules = {rule.stat_key: rule.points for rule in scoring_rules}
        supported_keys = set(STAT_TO_SCORING_KEY.values())
        for aliases in SCORING_KEY_ALIASES.values():
            supported_keys.update(aliases)
        self.unsupported_rules = [
            UnsupportedScoringRule(
                stat_key=stat_key,
                points=points,
                message=(
                    f"{stat_key} is configured in this league but is not currently "
                    "projected, so it contributes 0."
                ),
            )
            for stat_key, points in sorted(self.scoring_rules.items())
            if stat_key not in supported_keys
        ]

    def fantasy_points_per_game(self, projection: PlayerProjection) -> Decimal:
        return sum(
            (item.contribution for item in self.contributions(projection)),
            Decimal("0"),
        )

    def projected_fantasy_points(self, projection: PlayerProjection) -> Decimal:
        return self.fantasy_points_per_game(projection) * projection.games

    def contributions(self, projection: PlayerProjection) -> list[ScoringContribution]:
        contributions = []
        for stat_name, scoring_key in STAT_TO_SCORING_KEY.items():
            configured_stat_key = self._configured_stat_key(scoring_key)
            league_weight = (
                self.scoring_rules[configured_stat_key]
                if configured_stat_key
                else Decimal("0")
            )
            projection_value = getattr(projection, stat_name)
            applied_projection_value = projection_value or Decimal("0")
            contribution = applied_projection_value * league_weight
            contributions.append(
                ScoringContribution(
                    stat_name=stat_name,
                    scoring_key=scoring_key,
                    configured_stat_key=configured_stat_key,
                    projection_value=projection_value,
                    applied_projection_value=applied_projection_value,
                    league_weight=league_weight,
                    contribution=contribution,
                )
            )
        return contributions

    def _configured_stat_key(self, scoring_key: str) -> str | None:
        for candidate in SCORING_KEY_ALIASES.get(scoring_key, (scoring_key,)):
            if candidate in self.scoring_rules:
                return candidate
        return None
