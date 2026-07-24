from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.players.repository import PlayerRepository
from app.players.schemas import PlayerListResponse, PlayerRead
from app.players.service import PlayerNotFoundError, PlayerService
from app.shared.database.session import get_session

router = APIRouter(prefix="/players", tags=["players"])


def get_player_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlayerService:
    return PlayerService(PlayerRepository(session))


@router.get("", response_model=PlayerListResponse)
async def list_players(
    service: Annotated[PlayerService, Depends(get_player_service)],
    search: str | None = None,
    team: str | None = None,
    position: str | None = None,
    active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PlayerListResponse:
    players, total = await service.list_players(
        search=search,
        team=team,
        position=position,
        active=active,
        limit=limit,
        offset=offset,
    )
    return PlayerListResponse(
        items=[PlayerRead.model_validate(player) for player in players],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{player_id}", response_model=PlayerRead)
async def get_player(
    player_id: int,
    service: Annotated[PlayerService, Depends(get_player_service)],
):
    try:
        player = await service.get_player(player_id)
    except PlayerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="player not found",
        ) from exc

    return PlayerRead.model_validate(player)
