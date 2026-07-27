from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.projections.bootstrap.generator import (
    DEFAULT_AS_OF_DATE,
    DEFAULT_SEASON,
    DEFAULT_SOURCE_KEY,
    DEFAULT_SOURCE_NAME,
    default_basketball_reference_metadata_path,
    default_basketball_reference_sps_path,
    generate_bootstrap_projection_payload,
)
from app.projections.import_service import ProjectionImportMetadata, ProjectionImportService
from app.projections.repository import ProjectionRepository
from app.projections.schemas import (
    BootstrapProjectionImportResponse,
    BootstrapProjectionStatus,
    ProjectionPlayerListResponse,
    ProjectionSetListResponse,
    ProjectionSetRead,
    ProjectionSourceListResponse,
    ProjectionSourceRead,
    RawProjectionPlayerListResponse,
    RawProjectionSortField,
    SortDirection,
    SortField,
)
from app.projections.service import (
    LeagueConfigurationRequiredError,
    ProjectionService,
    ProjectionSetNotFoundError,
)
from app.shared.config.settings import get_settings
from app.shared.database.session import get_session

router = APIRouter(tags=["projections"])
BOOTSTRAP_DRAFT_READY_ELIGIBLE_PLAYER_THRESHOLD = 150


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


@router.get(
    "/projection-bootstrap/status",
    response_model=BootstrapProjectionStatus,
)
async def get_bootstrap_projection_status(
    service: Annotated[ProjectionService, Depends(get_projection_service)],
) -> BootstrapProjectionStatus:
    if not get_settings().enable_bootstrap_import:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bootstrap import disabled",
        )
    path = default_basketball_reference_sps_path()
    metadata_path = default_basketball_reference_metadata_path()
    bootstrap_exists, active_bootstrap_exists = (
        await service.repository.bootstrap_projection_set_summary(DEFAULT_SOURCE_KEY)
    )
    eligibility_summary = (
        await service.repository.active_bootstrap_projection_eligibility_summary(
            DEFAULT_SOURCE_KEY
        )
    )
    imported_player_count, players_with_eligibility_count = eligibility_summary or (0, 0)
    players_missing_eligibility_count = max(
        imported_player_count - players_with_eligibility_count,
        0,
    )
    projection_sets_count = await service.count_projection_sets()
    return BootstrapProjectionStatus(
        projection_sets_count=projection_sets_count,
        csv_available=path.exists(),
        csv_path=str(path),
        metadata_available=metadata_path.exists(),
        metadata_path=str(metadata_path),
        bootstrap_projection_set_exists=bootstrap_exists,
        active_bootstrap_projection_set_exists=active_bootstrap_exists,
        imported_player_count=imported_player_count,
        players_with_eligibility_count=players_with_eligibility_count,
        players_missing_eligibility_count=players_missing_eligibility_count,
        draft_ready=(
            active_bootstrap_exists
            and players_with_eligibility_count
            >= BOOTSTRAP_DRAFT_READY_ELIGIBLE_PLAYER_THRESHOLD
        ),
        import_available=(
            path.exists()
            and metadata_path.exists()
            and projection_sets_count == 0
            and not bootstrap_exists
            and not active_bootstrap_exists
        ),
    )


@router.post(
    "/projection-bootstrap/import",
    response_model=BootstrapProjectionImportResponse,
)
async def import_bootstrap_projection_data(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BootstrapProjectionImportResponse:
    if not get_settings().enable_bootstrap_import:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bootstrap import disabled",
        )
    repository = ProjectionRepository(session)
    projection_sets_count = await repository.count_projection_sets()
    bootstrap_exists, _active_bootstrap_exists = (
        await repository.bootstrap_projection_set_summary(DEFAULT_SOURCE_KEY)
    )
    if projection_sets_count > 0 or bootstrap_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="projection data already imported",
        )
    await session.rollback()

    path = default_basketball_reference_sps_path()
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="bootstrap CSV not found",
        )
    metadata_path = default_basketball_reference_metadata_path()
    if not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="bootstrap metadata CSV not found",
        )

    payload = generate_bootstrap_projection_payload(path, metadata_path)
    issues = (*payload.parse_result.rejected_issues, *payload.metadata_result.rejected_issues)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[issue.message for issue in issues],
        )
    metadata = ProjectionImportMetadata(
        source_key=DEFAULT_SOURCE_KEY,
        source_name=DEFAULT_SOURCE_NAME,
        source_description=(
            "Temporary Basketball Reference SPS bootstrap source for validating "
            "Fantasy GM's projection import pipeline."
        ),
        season=DEFAULT_SEASON,
        as_of_date=DEFAULT_AS_OF_DATE,
        activate=True,
        notes=(
            "Bootstrap import generated from Basketball Reference SPS per-36 "
            "statistics using fixed games and minutes assumptions."
        ),
    )
    result = await ProjectionImportService(session).import_players(
        players=payload.players,
        metadata=metadata,
        rows_read=payload.diagnostics.rows_read,
    )
    return BootstrapProjectionImportResponse(
        projection_set_id=result.projection_set_id,
        source_key=result.source_key,
        source_name=result.source_name,
        season=result.season,
        as_of_date=result.as_of_date,
        is_active=result.is_active,
        rows_imported=result.rows_imported,
        players_created=result.new_players_created,
        projection_rows_created=result.projection_rows_created,
    )


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
    "/projection-sets/{projection_set_id}/raw-players",
    response_model=RawProjectionPlayerListResponse,
)
async def list_raw_projection_players(
    projection_set_id: int,
    service: Annotated[ProjectionService, Depends(get_projection_service)],
    search: str | None = None,
    team: str | None = None,
    position: str | None = None,
    sort: RawProjectionSortField = "player",
    direction: SortDirection = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RawProjectionPlayerListResponse:
    try:
        players, total = await service.list_raw_projection_players(
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

    return RawProjectionPlayerListResponse(
        items=players,
        total=total,
        limit=limit,
        offset=offset,
    )


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
