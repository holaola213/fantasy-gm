from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.projections.repository import ProjectionRepository
from app.projections.schemas import (
    ProjectionPlayerListResponse,
    ProjectionSetListResponse,
    ProjectionSetRead,
    ProjectionSourceListResponse,
    ProjectionSourceRead,
    SortDirection,
    SortField,
)
from app.projections.service import (
    LeagueConfigurationRequiredError,
    ProjectionService,
    ProjectionSetNotFoundError,
)
from app.shared.database.session import get_session

router = APIRouter(tags=["projections"])


def get_projection_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectionService:
    return ProjectionService(ProjectionRepository(session))


@router.get("/projection-sources", response_model=ProjectionSourceListResponse)
async def list_projection_sources(
    service: Annotated[ProjectionService, Depends(get_projection_service)],
) -> ProjectionSourceListResponse:
    sources = await service.list_sources()
    return ProjectionSourceListResponse(
        items=[ProjectionSourceRead.model_validate(source) for source in sources]
    )


@router.get("/projection-sets", response_model=ProjectionSetListResponse)
async def list_projection_sets(
    service: Annotated[ProjectionService, Depends(get_projection_service)],
) -> ProjectionSetListResponse:
    projection_sets = await service.list_projection_sets()
    return ProjectionSetListResponse(items=projection_sets)


@router.get("/projection-sets/{projection_set_id}", response_model=ProjectionSetRead)
async def get_projection_set(
    projection_set_id: int,
    service: Annotated[ProjectionService, Depends(get_projection_service)],
) -> ProjectionSetRead:
    try:
        projection_set = await service.get_projection_set(projection_set_id)
    except ProjectionSetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="projection set not found",
        ) from exc

    return projection_set


@router.get(
    "/projection-sets/{projection_set_id}/players",
    response_model=ProjectionPlayerListResponse,
)
async def list_projection_players(
    projection_set_id: int,
    service: Annotated[ProjectionService, Depends(get_projection_service)],
    search: str | None = None,
    team: str | None = None,
    position: str | None = None,
    sort: SortField = "projected_fantasy_points",
    direction: SortDirection = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectionPlayerListResponse:
    try:
        players, total = await service.list_projection_players(
            projection_set_id=projection_set_id,
            search=search,
            team=team,
            position=position,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )
    except ProjectionSetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="projection set not found",
        ) from exc
    except LeagueConfigurationRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league configuration required",
        ) from exc

    return ProjectionPlayerListResponse(
        items=players,
        total=total,
        limit=limit,
        offset=offset,
    )
