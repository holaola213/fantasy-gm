from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.draft_assistant.repository import DraftAssistantRepository
from app.draft_assistant.roster_assignment import UnsupportedRosterSlotError
from app.draft_assistant.schemas import DraftAssistantResponse
from app.draft_assistant.service import (
    ActiveDraftRequiredError,
    DraftAssistantService,
    UserFantasyTeamRequiredError,
)
from app.shared.database.session import get_session
from app.valuations.replacement import InsufficientEligiblePlayerPoolError
from app.valuations.service import (
    ActiveProjectionSetRequiredError,
    LeagueConfigurationRequiredError,
    ProjectionSetNotFoundError,
)

router = APIRouter(prefix="/draft/assistant", tags=["draft assistant"])


def get_draft_assistant_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DraftAssistantService:
    return DraftAssistantService(DraftAssistantRepository(session))


@router.get("", response_model=DraftAssistantResponse)
async def get_draft_assistant(
    service: Annotated[DraftAssistantService, Depends(get_draft_assistant_service)],
    limit_per_section: Annotated[int, Query(ge=1, le=10)] = 5,
    include_assignments: bool = True,
) -> DraftAssistantResponse:
    try:
        return await service.get_assistant(
            limit_per_section=limit_per_section,
            include_assignments=include_assignments,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ActiveDraftRequiredError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active draft required",
        )
    if isinstance(exc, UserFantasyTeamRequiredError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="user fantasy team required",
        )
    if isinstance(exc, LeagueConfigurationRequiredError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league configuration required",
        )
    if isinstance(exc, (ActiveProjectionSetRequiredError, ProjectionSetNotFoundError)):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active projection set required",
        )
    if isinstance(exc, UnsupportedRosterSlotError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="unsupported roster slot",
        )
    if isinstance(exc, InsufficientEligiblePlayerPoolError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="insufficient eligible player pool",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="draft assistant could not be calculated",
    )
