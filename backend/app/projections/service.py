from app.leagues.model import League
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.repository import ProjectionRepository
from app.projections.schemas import (
    ProjectionPlayerRead,
    ProjectionSetRead,
    RawProjectionPlayerRead,
    RawProjectionSortField,
    SortDirection,
    SortField,
)
from app.shared.scoring import FantasyScorer


class ProjectionSetNotFoundError(Exception):
    pass


class LeagueConfigurationRequiredError(Exception):
    pass


class ProjectionService:
    def __init__(self, repository: ProjectionRepository) -> None:
        self.repository = repository

    async def list_sources(self) -> list[ProjectionSource]:
        return await self.repository.list_sources()

    async def list_projection_sets(self) -> list[ProjectionSetRead]:
        rows = await self.repository.list_projection_sets()
        return [
            self._build_projection_set_read(projection_set, player_count)
            for projection_set, player_count in rows
        ]

    async def get_projection_set(self, projection_set_id: int) -> ProjectionSetRead:
        projection_set = await self.repository.get_projection_set(projection_set_id)
        if projection_set is None:
            raise ProjectionSetNotFoundError
        player_count = await self.repository.count_projection_players(projection_set_id)
        return self._build_projection_set_read(projection_set, player_count)

    async def count_projection_sets(self) -> int:
        return await self.repository.count_projection_sets()

    async def list_raw_projection_players(
        self,
        *,
        projection_set_id: int,
        search: str | None,
        team: str | None,
        position: str | None,
        sort: RawProjectionSortField,
        direction: SortDirection,
        limit: int,
        offset: int,
    ) -> tuple[list[RawProjectionPlayerRead], int]:
        projection_set = await self.repository.get_projection_set(projection_set_id)
        if projection_set is None:
            raise ProjectionSetNotFoundError

        rows, total = await self.repository.list_raw_projection_players(
            projection_set_id=projection_set_id,
            search=search,
            team=team,
            position=position,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )
        return [
            self._build_raw_projection_player_read(projection, player)
            for projection, player in rows
        ], total

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
        scorer = FantasyScorer(league.scoring_rules)
        items = [
            self._build_projection_player_read(projection, player, scorer)
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

    def _build_projection_player_read(
        self,
        projection: PlayerProjection,
        player,
        scorer: FantasyScorer,
    ) -> ProjectionPlayerRead:
        fantasy_points_per_game = scorer.fantasy_points_per_game(projection)
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

    def _build_raw_projection_player_read(
        self,
        projection: PlayerProjection,
        player,
    ) -> RawProjectionPlayerRead:
        return RawProjectionPlayerRead(
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
            points=projection.points,
        )

    def _build_projection_set_read(
        self,
        projection_set: ProjectionSet,
        player_count: int,
    ) -> ProjectionSetRead:
        return ProjectionSetRead.model_validate(
            {
                **projection_set.__dict__,
                "source": projection_set.source,
                "player_count": player_count,
            }
        )
