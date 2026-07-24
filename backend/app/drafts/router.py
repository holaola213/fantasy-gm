from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.drafts.repository import DraftRepository
from app.drafts.schemas import (
    AvailablePlayerListResponse,
    DraftBoardResponse,
    DraftCreate,
    DraftPickCreate,
    DraftPickRead,
    DraftSessionRead,
    DraftSetupUpdate,
    DraftSortField,
    DraftTeamDetailResponse,
    EligibilityRead,
    FantasyTeamRead,
    PositionKey,
    SortDirection,
)
from app.drafts.service import (
    ActiveProjectionSetRequiredError,
    CompletedDraftCannotBeDeletedError,
    DraftConflictError,
    DraftInProgressRequiredError,
    DraftNotFoundError,
    DraftPersistenceError,
    DraftService,
    DraftSetupRequiredError,
    LeagueConfigurationRequiredError,
    PlayerEligibilityRequiredError,
    PlayerUnavailableError,
)
from app.shared.database.session import get_session

router = APIRouter(tags=["draft"])


def get_draft_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DraftService:
    return DraftService(DraftRepository(session), session)


def conflict_response(exc: DraftConflictError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail)


@router.get("/draft", response_model=DraftSessionRead)
async def get_draft(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftSessionRead:
    try:
        return await service.get_draft()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc


@router.post("/draft", response_model=DraftSessionRead)
async def create_draft(
    payload: DraftCreate,
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftSessionRead:
    try:
        return await service.create_draft(payload)
    except LeagueConfigurationRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league configuration required",
        ) from exc
    except ActiveProjectionSetRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active projection set required",
        ) from exc
    except DraftConflictError as exc:
        raise conflict_response(exc) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft could not be saved",
        ) from exc


@router.put("/draft/setup", response_model=DraftSessionRead)
async def update_draft_setup(
    payload: DraftSetupUpdate,
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftSessionRead:
    try:
        return await service.update_setup(payload)
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except DraftConflictError as exc:
        raise conflict_response(exc) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft could not be saved",
        ) from exc


@router.post("/draft/start", response_model=DraftSessionRead)
async def start_draft(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftSessionRead:
    try:
        return await service.start_draft()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except DraftSetupRequiredError as exc:
        raise conflict_response(exc) from exc
    except DraftConflictError as exc:
        raise conflict_response(exc) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft could not be saved",
        ) from exc


@router.post("/draft/reset", response_model=DraftSessionRead)
async def reset_draft(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftSessionRead:
    try:
        return await service.reset_draft()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft could not be reset",
        ) from exc


@router.delete("/draft", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> None:
    try:
        await service.delete_draft()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except CompletedDraftCannotBeDeletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="completed draft cannot be deleted",
        ) from exc
    except DraftConflictError as exc:
        raise conflict_response(exc) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft could not be deleted",
        ) from exc


@router.get("/draft/board", response_model=DraftBoardResponse)
async def get_draft_board(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftBoardResponse:
    try:
        return await service.get_board()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc


@router.get("/draft/teams", response_model=list[FantasyTeamRead])
async def list_draft_teams(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> list[FantasyTeamRead]:
    try:
        return await service.list_teams()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc


@router.get("/draft/teams/{fantasy_team_id}", response_model=DraftTeamDetailResponse)
async def get_draft_team(
    fantasy_team_id: int,
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftTeamDetailResponse:
    try:
        return await service.get_team(fantasy_team_id)
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc


@router.get("/draft/available-players", response_model=AvailablePlayerListResponse)
async def list_available_players(
    service: Annotated[DraftService, Depends(get_draft_service)],
    search: str | None = None,
    team: str | None = None,
    position: PositionKey | None = None,
    sort: DraftSortField = "projected_fantasy_points",
    direction: SortDirection = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AvailablePlayerListResponse:
    try:
        players, total = await service.list_available_players(
            search=search,
            team=team,
            position=position,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except LeagueConfigurationRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league configuration required",
        ) from exc
    return AvailablePlayerListResponse(
        items=players,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/draft/picks", response_model=DraftPickRead)
async def create_draft_pick(
    payload: DraftPickCreate,
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftPickRead:
    try:
        return await service.create_pick(payload.player_id)
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except DraftInProgressRequiredError as exc:
        raise conflict_response(exc) from exc
    except PlayerUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="player unavailable",
        ) from exc
    except PlayerEligibilityRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="player eligibility required",
        ) from exc
    except DraftConflictError as exc:
        raise conflict_response(exc) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft pick could not be saved",
        ) from exc


@router.delete("/draft/picks/latest", response_model=DraftPickRead)
async def undo_latest_pick(
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> DraftPickRead:
    try:
        return await service.undo_latest_pick()
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="draft not found",
        ) from exc
    except DraftConflictError as exc:
        raise conflict_response(exc) from exc
    except DraftPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft pick could not be removed",
        ) from exc


@router.get("/players/{player_id}/eligibility", response_model=EligibilityRead)
async def get_player_eligibility(
    player_id: int,
    service: Annotated[DraftService, Depends(get_draft_service)],
) -> EligibilityRead:
    try:
        return await service.get_player_eligibility(player_id)
    except LeagueConfigurationRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league configuration required",
        ) from exc
