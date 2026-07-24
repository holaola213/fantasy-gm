from decimal import Decimal

from app.leagues.model import League
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.repository import ProjectionRepository
from app.projections.schemas import ProjectionPlayerRead, SortDirection, SortField


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


class ProjectionSetNotFoundError(Exception):
    pass


class LeagueConfigurationRequiredError(Exception):
    pass


class ProjectionService:
    def __init__(self, repository: ProjectionRepository) -> None:
        self.repository = repository

    async def list_sources(self) -> list[ProjectionSource]:
        return await self.repository.list_sources()

    async def list_projection_sets(self) -> list[ProjectionSet]:
        return await self.repository.list_projection_sets()

    async def get_projection_set(self, projection_set_id: int) -> ProjectionSet:
        projection_set = await self.repository.get_projection_set(projection_set_id)
        if projection_set is None:
            raise ProjectionSetNotFoundError
        return projection_set

    async def list_projection_players(
        self,
        *,
        projection_set_id: int,
        search: str | None,
        team: str | None,
        position: str | None,
        sort: SortField,
        direction: SortDirection,
        limit: int,
        offset: int,
    ) -> tuple[list[ProjectionPlayerRead], int]:
        projection_set = await self.repository.get_projection_set(projection_set_id)
        if projection_set is None:
            raise ProjectionSetNotFoundError

        league = await self.repository.get_singleton_league()
        if league is None:
            raise LeagueConfigurationRequiredError

        fetch_limit = None if sort in {
            "fantasy_points_per_game",
            "projected_fantasy_points",
        } else limit
        fetch_offset = 0 if sort in {
            "fantasy_points_per_game",
            "projected_fantasy_points",
        } else offset
        rows, total = await self.repository.list_projection_players(
            projection_set_id=projection_set_id,
            search=search,
            team=team,
            position=position,
            sort=sort,
            direction=direction,
            limit=fetch_limit,
            offset=fetch_offset,
        )
        scoring_rules = self._scoring_rules_by_key(league)
        items = [
            self._build_projection_player_read(projection, player, scoring_rules)
            for projection, player in rows
        ]
        if sort in {"fantasy_points_per_game", "projected_fantasy_points"}:
            reverse = direction == "desc"
            items = sorted(items, key=lambda item: (item.full_name, item.player_id))
            items = sorted(
                items,
                key=lambda item: getattr(item, sort),
                reverse=reverse,
            )
            items = items[offset : offset + limit]
        return items, total

    def _scoring_rules_by_key(self, league: League) -> dict[str, Decimal]:
        return {rule.stat_key: rule.points for rule in league.scoring_rules}

    def _build_projection_player_read(
        self,
        projection: PlayerProjection,
        player,
        scoring_rules: dict[str, Decimal],
    ) -> ProjectionPlayerRead:
        fantasy_points_per_game = self._fantasy_points_per_game(
            projection,
            scoring_rules,
        )
        return ProjectionPlayerRead(
            player_id=player.id,
            full_name=player.full_name,
            team=player.team,
            primary_position=player.primary_position,
            games=projection.games,
            minutes_per_game=projection.minutes_per_game,
            fgm=projection.fgm,
            fga=projection.fga,
            ftm=projection.ftm,
            fta=projection.fta,
            rebounds=projection.rebounds,
            assists=projection.assists,
            steals=projection.steals,
            blocks=projection.blocks,
            turnovers=projection.turnovers,
            fantasy_points_per_game=fantasy_points_per_game,
            projected_fantasy_points=fantasy_points_per_game * projection.games,
        )

    def _fantasy_points_per_game(
        self,
        projection: PlayerProjection,
        scoring_rules: dict[str, Decimal],
    ) -> Decimal:
        total = Decimal("0")
        for stat_name, scoring_key in STAT_TO_SCORING_KEY.items():
            stat_value = getattr(projection, stat_name)
            scoring_value = scoring_rules.get(scoring_key, Decimal("0"))
            total += stat_value * scoring_value
        return total
