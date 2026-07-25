from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.leagues.model import League, ScoringRule
from app.leagues.repository import SINGLETON_LEAGUE_ID
from app.players.model import Player
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.schemas import SortDirection, SortField


class ProjectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sources(self) -> list[ProjectionSource]:
        result = await self.session.scalars(
            select(ProjectionSource).order_by(ProjectionSource.key, ProjectionSource.id)
        )
        return list(result.all())

    async def list_projection_sets(self) -> list[tuple[ProjectionSet, int]]:
        result = await self.session.execute(
            select(ProjectionSet, func.count(PlayerProjection.id))
            .outerjoin(PlayerProjection)
            .options(selectinload(ProjectionSet.source))
            .group_by(ProjectionSet.id)
            .order_by(
                desc(ProjectionSet.is_active),
                desc(ProjectionSet.as_of_date),
                desc(ProjectionSet.imported_at),
                ProjectionSet.id,
            )
        )
        return [(projection_set, player_count) for projection_set, player_count in result.all()]

    async def get_projection_set(self, projection_set_id: int) -> ProjectionSet | None:
        return await self.session.get(
            ProjectionSet,
            projection_set_id,
            options=[selectinload(ProjectionSet.source)],
        )

    async def count_projection_players(self, projection_set_id: int) -> int:
        return (
            await self.session.scalar(
                select(func.count()).select_from(PlayerProjection).where(
                    PlayerProjection.projection_set_id == projection_set_id
                )
            )
            or 0
        )

    async def get_singleton_league(self) -> League | None:
        return await self.session.get(
            League,
            SINGLETON_LEAGUE_ID,
            options=[selectinload(League.scoring_rules)],
        )

    async def list_projection_players(
        self,
        *,
        projection_set_id: int,
        search: str | None,
        team: str | None,
        position: str | None,
        sort: SortField,
        direction: SortDirection,
        limit: int | None,
        offset: int,
    ) -> tuple[list[tuple[PlayerProjection, Player]], int]:
        filtered_query = self._apply_player_filters(
            select(PlayerProjection, Player).join(Player),
            projection_set_id=projection_set_id,
            search=search,
            team=team,
            position=position,
        )
        total_query = self._apply_player_filters(
            select(func.count()).select_from(PlayerProjection).join(Player),
            projection_set_id=projection_set_id,
            search=search,
            team=team,
            position=position,
        )

        total = await self.session.scalar(total_query)
        ordered_query = self._apply_sort(filtered_query, sort=sort, direction=direction)
        if limit is not None:
            ordered_query = ordered_query.limit(limit).offset(offset)
        result = await self.session.execute(ordered_query)
        return list(result.all()), total or 0

    def _apply_player_filters(
        self,
        query: Select,
        *,
        projection_set_id: int,
        search: str | None,
        team: str | None,
        position: str | None,
    ) -> Select:
        query = query.where(PlayerProjection.projection_set_id == projection_set_id)
        if search:
            query = query.where(Player.full_name.ilike(f"%{search}%"))
        if team:
            query = query.where(func.lower(Player.team) == team.lower())
        if position:
            query = query.where(func.lower(Player.primary_position) == position.lower())
        return query

    def _apply_sort(
        self,
        query: Select,
        *,
        sort: SortField,
        direction: SortDirection,
    ) -> Select:
        sort_columns = {
            "player": Player.full_name,
            "team": Player.team,
            "position": Player.primary_position,
            "games": PlayerProjection.games,
            "minutes_per_game": PlayerProjection.minutes_per_game,
        }
        column = sort_columns.get(sort, Player.full_name)
        primary_order = desc(column) if direction == "desc" else asc(column)
        return query.order_by(primary_order, Player.full_name, Player.id)

    async def get_source_by_key(self, key: str) -> ProjectionSource | None:
        result = await self.session.scalars(
            select(ProjectionSource).where(ProjectionSource.key == key)
        )
        return result.one_or_none()

    async def get_projection_set_by_identity(
        self,
        *,
        source_id: int,
        season: int,
        projection_type: str,
        as_of_date,
    ) -> ProjectionSet | None:
        result = await self.session.scalars(
            select(ProjectionSet).where(
                ProjectionSet.source_id == source_id,
                ProjectionSet.season == season,
                ProjectionSet.projection_type == projection_type,
                ProjectionSet.as_of_date == as_of_date,
            )
        )
        return result.one_or_none()
