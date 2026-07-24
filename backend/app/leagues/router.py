from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.leagues.repository import LeagueRepository
from app.leagues.schemas import LeagueRead, LeagueUpdate
from app.leagues.service import (
    LeagueConfigurationLockedError,
    LeagueNotFoundError,
    LeaguePersistenceError,
    LeagueService,
)
from app.shared.database.session import get_session

router = APIRouter(prefix="/league", tags=["league"])


def get_league_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeagueService:
    return LeagueService(LeagueRepository(session), session)


@router.get("", response_model=LeagueRead)
async def get_league(
    service: Annotated[LeagueService, Depends(get_league_service)],
) -> LeagueRead:
    try:
        league = await service.get_league()
    except LeagueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="league configuration not found",
        ) from exc

    return LeagueRead.model_validate(league)


@router.put("", response_model=LeagueRead)
async def put_league(
    payload: LeagueUpdate,
    service: Annotated[LeagueService, Depends(get_league_service)],
) -> LeagueRead:
    try:
        league = await service.replace_league(payload)
    except LeagueConfigurationLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league configuration is locked while a draft is active",
        ) from exc
    except LeaguePersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="league configuration could not be saved",
        ) from exc

    return LeagueRead.model_validate(league)
