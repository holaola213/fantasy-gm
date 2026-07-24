from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.players.model import Player


class PlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_players(
        self,
        *,
        search: str | None,
        team: str | None,
        position: str | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Player], int]:
        filtered_query = self._apply_filters(
            select(Player),
            search=search,
            team=team,
            position=position,
            active=active,
        )
        total_query = self._apply_filters(
            select(func.count()).select_from(Player),
            search=search,
            team=team,
            position=position,
            active=active,
        )

        total = await self.session.scalar(total_query)
        result = await self.session.scalars(
            filtered_query.order_by(Player.full_name, Player.id)
            .limit(limit)
            .offset(offset)
        )

        return list(result.all()), total or 0

    async def get_player(self, player_id: int) -> Player | None:
        return await self.session.get(Player, player_id)

    def _apply_filters(
        self,
        query: Select[tuple[Player]] | Select[tuple[int]],
        *,
        search: str | None,
        team: str | None,
        position: str | None,
        active: bool | None,
    ):
        if search:
            query = query.where(Player.full_name.ilike(f"%{search}%"))
        if team:
            query = query.where(func.lower(Player.team) == team.lower())
        if position:
            query = query.where(
                func.lower(Player.primary_position) == position.lower()
            )
        if active is not None:
            query = query.where(Player.is_active.is_(active))

        return query
