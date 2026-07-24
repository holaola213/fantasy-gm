from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.session import get_session
from app.valuations.replacement import (
    InsufficientEligiblePlayerPoolError,
    UnsupportedRosterSlotError,
)
from app.valuations.repository import ValuationRepository
from app.valuations.schemas import (
    PlayerValuationRead,
    ReplacementLevelsResponse,
    SortDirection,
    ValuationListResponse,
    ValuationSortField,
)
from app.valuations.service import (
    ActiveProjectionSetRequiredError,
    ConflictingProjectionSetError,
    DraftRequiredError,
    LeagueConfigurationRequiredError,
    PlayerValuationNotFoundError,
    ProjectionSetNotFoundError,
    ValuationService,
)

router = APIRouter(tags=["valuations"])


def get_valuation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ValuationService:
    return ValuationService(ValuationRepository(session))


@router.get("/valuations", response_model=ValuationListResponse)
async def list_valuations(
    service: Annotated[ValuationService, Depends(get_valuation_service)],
    projection_set_id: int | None = None,
    available_only: bool = False,
    search: str | None = None,
    team: str | None = None,
    position: str | None = None,
    sort: ValuationSortField = "overall_rank",
    direction: SortDirection = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ValuationListResponse:
    try:
        items, total, projection_set = await service.list_valuations(
            projection_set_id=projection_set_id,
            available_only=available_only,
            search=search,
            team=team,
            position=position,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return ValuationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        projection_set_id=projection_set.id,
        projection_set_name=projection_set.name,
        projection_set_as_of_date=projection_set.as_of_date,
    )


@router.get("/valuations/replacement-levels", response_model=ReplacementLevelsResponse)
async def get_replacement_levels(
    service: Annotated[ValuationService, Depends(get_valuation_service)],
    projection_set_id: int | None = None,
) -> ReplacementLevelsResponse:
    try:
        return await service.replacement_levels(projection_set_id=projection_set_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/players/{player_id}/valuation", response_model=PlayerValuationRead)
async def get_player_valuation(
    player_id: int,
    service: Annotated[ValuationService, Depends(get_valuation_service)],
    projection_set_id: int | None = None,
) -> PlayerValuationRead:
    try:
        return await service.player_valuation(
            player_id=player_id,
            projection_set_id=projection_set_id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LeagueConfigurationRequiredError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="league configuration required")
    if isinstance(exc, ActiveProjectionSetRequiredError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active projection set required")
    if isinstance(exc, DraftRequiredError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft required")
    if isinstance(exc, ConflictingProjectionSetError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="projection_set_id conflicts with current draft")
    if isinstance(exc, ProjectionSetNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="projection set not found")
    if isinstance(exc, UnsupportedRosterSlotError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="unsupported roster slot")
    if isinstance(exc, InsufficientEligiblePlayerPoolError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient eligible player pool")
    if isinstance(exc, PlayerValuationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player valuation not found")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="valuation could not be calculated")
