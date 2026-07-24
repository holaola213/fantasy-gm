from app.players.model import Player
from app.players.repository import PlayerRepository


class PlayerNotFoundError(Exception):
    pass


class PlayerService:
    def __init__(self, repository: PlayerRepository) -> None:
        self.repository = repository

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
        return await self.repository.list_players(
            search=search,
            team=team,
            position=position,
            active=active,
            limit=limit,
            offset=offset,
        )

    async def get_player(self, player_id: int) -> Player:
        player = await self.repository.get_player(player_id)
        if player is None:
            raise PlayerNotFoundError
        return player
