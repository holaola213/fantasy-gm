from datetime import UTC, datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.drafts.compatibility import (
    calculate_draft_rounds,
    compatible_roster_slots,
    snake_pick_details,
)
from app.drafts.model import DraftPick, DraftSession, FantasyTeam
from app.drafts.repository import DraftRepository
from app.drafts.schemas import (
    AvailablePlayerRead,
    DraftBoardResponse,
    DraftCreate,
    DraftPickRead,
    DraftSessionRead,
    DraftSetupUpdate,
    DraftTeamDetailResponse,
    EligibilityRead,
    FantasyTeamRead,
)
from app.leagues.repository import SINGLETON_LEAGUE_ID
from app.players.model import Player, PlayerEligibility
from app.projections.model import PlayerProjection
from app.shared.scoring import FantasyScorer


class DraftNotFoundError(Exception):
    pass


class LeagueConfigurationRequiredError(Exception):
    pass


class ActiveProjectionSetRequiredError(Exception):
    pass


class DraftConflictError(Exception):
    detail = "draft conflict"


class DraftSetupRequiredError(DraftConflictError):
    detail = "draft must be in setup"


class DraftInProgressRequiredError(DraftConflictError):
    detail = "draft must be in progress"


class CompletedDraftCannotBeDeletedError(DraftConflictError):
    detail = "completed draft cannot be deleted"


class PlayerUnavailableError(DraftConflictError):
    detail = "player unavailable"


class PlayerEligibilityRequiredError(DraftConflictError):
    detail = "player eligibility required"


class DraftPersistenceError(Exception):
    pass


class DraftService:
    def __init__(self, repository: DraftRepository, session: AsyncSession) -> None:
        self.repository = repository
        self.session = session

    async def get_draft(self) -> DraftSessionRead:
        draft = await self.repository.get_latest_draft()
        if draft is None:
            raise DraftNotFoundError
        return await self._draft_read(draft)

    async def create_draft(self, payload: DraftCreate) -> DraftSessionRead:
        try:
            async with self.session.begin():
                existing = await self.repository.get_current_draft()
                if existing is not None:
                    raise DraftConflictError
                league = await self.repository.get_singleton_league()
                if league is None:
                    raise LeagueConfigurationRequiredError
                projection_set = await self.repository.get_deterministic_active_projection_set()
                if projection_set is None:
                    raise ActiveProjectionSetRequiredError
                if len(payload.teams) != league.team_count:
                    raise DraftConflictError
                rounds = calculate_draft_rounds(
                    {slot.slot_key: slot.count for slot in league.roster_slots}
                )
                draft = await self.repository.create_draft_session(
                    league_id=SINGLETON_LEAGUE_ID,
                    projection_set_id=projection_set.id,
                    name=payload.name,
                    season=league.season,
                    team_count=league.team_count,
                    rounds=rounds,
                )
                await self._replace_setup_teams(draft, payload)
                draft = await self.repository.get_draft(draft.id)
                if draft is None:
                    raise RuntimeError("draft creation failed")
                return await self._draft_read(draft)
        except DraftConflictError:
            raise
        except (LeagueConfigurationRequiredError, ActiveProjectionSetRequiredError):
            raise
        except SQLAlchemyError as exc:
            raise DraftPersistenceError from exc

    async def update_setup(self, payload: DraftSetupUpdate) -> DraftSessionRead:
        try:
            async with self.session.begin():
                draft = await self.repository.get_latest_draft_for_update()
                if draft is None:
                    raise DraftNotFoundError
                if draft.status != "setup":
                    raise DraftSetupRequiredError
                if len(payload.teams) != draft.team_count:
                    raise DraftConflictError
                draft.name = payload.name
                await self._replace_setup_teams(draft, payload)
                draft = await self.repository.get_draft(draft.id)
                if draft is None:
                    raise RuntimeError("draft update failed")
                return await self._draft_read(draft)
        except (DraftNotFoundError, DraftConflictError):
            raise
        except SQLAlchemyError as exc:
            raise DraftPersistenceError from exc

    async def start_draft(self) -> DraftSessionRead:
        try:
            async with self.session.begin():
                draft = await self.repository.get_latest_draft_for_update()
                if draft is None:
                    raise DraftNotFoundError
                if draft.status != "setup":
                    raise DraftSetupRequiredError
                self._validate_setup_teams(draft)
                draft.status = "in_progress"
                draft.started_at = datetime.now(UTC)
                draft = await self.repository.get_draft(draft.id)
                if draft is None:
                    raise RuntimeError("draft start failed")
                return await self._draft_read(draft)
        except (DraftNotFoundError, DraftConflictError):
            raise
        except SQLAlchemyError as exc:
            raise DraftPersistenceError from exc

    async def delete_draft(self) -> None:
        try:
            async with self.session.begin():
                draft = await self.repository.get_latest_draft_for_update()
                if draft is None:
                    raise DraftNotFoundError
                if draft.status == "completed":
                    raise CompletedDraftCannotBeDeletedError
                await self.repository.delete_draft(draft)
        except (DraftNotFoundError, DraftConflictError):
            raise
        except SQLAlchemyError as exc:
            raise DraftPersistenceError from exc

    async def get_board(self) -> DraftBoardResponse:
        draft = await self.repository.get_latest_draft()
        if draft is None:
            raise DraftNotFoundError
        return await self._board_response(draft)

    async def list_teams(self) -> list[FantasyTeamRead]:
        draft = await self.repository.get_latest_draft()
        if draft is None:
            raise DraftNotFoundError
        return [FantasyTeamRead.model_validate(team) for team in draft.teams]

    async def get_team(self, fantasy_team_id: int) -> DraftTeamDetailResponse:
        draft = await self.repository.get_latest_draft()
        if draft is None:
            raise DraftNotFoundError
        team = next((item for item in draft.teams if item.id == fantasy_team_id), None)
        if team is None:
            raise DraftNotFoundError
        picks = [pick for pick in draft.picks if pick.fantasy_team_id == team.id]
        return DraftTeamDetailResponse(
            team=FantasyTeamRead.model_validate(team),
            picks=await self._pick_reads(draft, picks),
        )

    async def create_pick(self, player_id: int) -> DraftPickRead:
        try:
            async with self.session.begin():
                draft = await self.repository.get_latest_draft_for_update()
                if draft is None:
                    raise DraftNotFoundError
                if draft.status != "in_progress":
                    raise DraftInProgressRequiredError
                pick_count = await self.repository.count_picks(draft.id)
                next_overall = pick_count + 1
                total_picks = draft.team_count * draft.rounds
                if next_overall > total_picks:
                    raise DraftConflictError
                if not await self.repository.player_is_available(
                    draft=draft,
                    player_id=player_id,
                ):
                    raise PlayerUnavailableError
                eligibilities = await self.repository.get_player_eligibilities(player_id)
                if not eligibilities:
                    raise PlayerEligibilityRequiredError
                round_number, pick_in_round, draft_position = snake_pick_details(
                    next_overall,
                    draft.team_count,
                )
                team = await self.repository.get_team_by_position(
                    draft_session_id=draft.id,
                    draft_position=draft_position,
                )
                if team is None:
                    raise DraftConflictError
                pick = await self.repository.create_pick(
                    draft_session_id=draft.id,
                    fantasy_team_id=team.id,
                    player_id=player_id,
                    round_number=round_number,
                    pick_in_round=pick_in_round,
                    overall_pick=next_overall,
                )
                if next_overall == total_picks:
                    draft.status = "completed"
                    draft.completed_at = datetime.now(UTC)
                draft = await self.repository.get_draft(draft.id)
                if draft is None:
                    raise RuntimeError("draft pick failed")
                saved = next(item for item in draft.picks if item.id == pick.id)
                return (await self._pick_reads(draft, [saved]))[0]
        except (DraftNotFoundError, DraftConflictError):
            raise
        except SQLAlchemyError as exc:
            raise DraftPersistenceError from exc

    async def undo_latest_pick(self) -> DraftPickRead:
        try:
            async with self.session.begin():
                draft = await self.repository.get_latest_draft()
                if draft is None:
                    raise DraftNotFoundError
                latest = await self.repository.get_latest_pick(draft.id)
                if latest is None:
                    raise DraftConflictError
                draft = await self.repository.get_draft(draft.id)
                if draft is None:
                    raise DraftNotFoundError
                pick_read = (await self._pick_reads(draft, [latest]))[0]
                await self.repository.delete_pick(latest)
                if draft.status == "completed":
                    draft.status = "in_progress"
                    draft.completed_at = None
                return pick_read
        except (DraftNotFoundError, DraftConflictError):
            raise
        except SQLAlchemyError as exc:
            raise DraftPersistenceError from exc

    async def list_available_players(
        self,
        *,
        search: str | None,
        team: str | None,
        position: str | None,
        sort: str,
        direction: str,
        limit: int,
        offset: int,
    ) -> tuple[list[AvailablePlayerRead], int]:
        draft = await self.repository.get_latest_draft()
        if draft is None:
            raise DraftNotFoundError
        league = await self.repository.get_singleton_league()
        if league is None:
            raise LeagueConfigurationRequiredError

        fantasy_sort = sort in {"fantasy_points_per_game", "projected_fantasy_points"}
        rows, total = await self.repository.list_available_players(
            draft=draft,
            search=search,
            team=team,
            position=position,
            sort=sort,
            direction=direction,
            limit=None if fantasy_sort else limit,
            offset=0 if fantasy_sort else offset,
        )
        items = await self._available_player_reads(draft, rows)
        if fantasy_sort:
            reverse = direction == "desc"
            items = sorted(items, key=lambda item: (item.full_name, item.player_id))
            items = sorted(items, key=lambda item: getattr(item, sort), reverse=reverse)
            items = items[offset : offset + limit]
        return items, total

    async def get_player_eligibility(self, player_id: int) -> EligibilityRead:
        league = await self.repository.get_singleton_league()
        if league is None:
            raise LeagueConfigurationRequiredError
        positions = await self.repository.get_player_eligibilities(player_id)
        configured_slots = self._configured_draft_slots(league)
        return EligibilityRead(
            player_id=player_id,
            eligible_positions=positions,
            compatible_roster_slots=compatible_roster_slots(positions, configured_slots),
        )

    async def _replace_setup_teams(
        self,
        draft: DraftSession,
        payload: DraftCreate | DraftSetupUpdate,
    ) -> None:
        self._validate_payload_team_count(payload, draft.team_count)
        teams = [
            FantasyTeam(
                draft_session_id=draft.id,
                name=team.name,
                draft_position=team.draft_position,
                is_user_team=team.draft_position == payload.user_draft_position,
            )
            for team in sorted(payload.teams, key=lambda item: item.draft_position)
        ]
        await self.repository.replace_teams(draft_session_id=draft.id, teams=teams)

    def _validate_payload_team_count(
        self,
        payload: DraftCreate | DraftSetupUpdate,
        team_count: int,
    ) -> None:
        if len(payload.teams) != team_count:
            raise DraftConflictError
        positions = {team.draft_position for team in payload.teams}
        if positions != set(range(1, team_count + 1)):
            raise DraftConflictError

    def _validate_setup_teams(self, draft: DraftSession) -> None:
        if len(draft.teams) != draft.team_count:
            raise DraftConflictError
        positions = {team.draft_position for team in draft.teams}
        if positions != set(range(1, draft.team_count + 1)):
            raise DraftConflictError
        if sum(1 for team in draft.teams if team.is_user_team) != 1:
            raise DraftConflictError

    async def _draft_read(self, draft: DraftSession) -> DraftSessionRead:
        pick_count = len(draft.picks)
        total_picks = draft.team_count * draft.rounds
        next_pick = pick_count + 1 if pick_count < total_picks else None
        current_round = None
        current_pick_in_round = None
        if next_pick is not None:
            current_round, current_pick_in_round, _ = snake_pick_details(
                next_pick,
                draft.team_count,
            )
        return DraftSessionRead(
            id=draft.id,
            league_id=draft.league_id,
            projection_set_id=draft.projection_set_id,
            name=draft.name,
            season=draft.season,
            draft_type=draft.draft_type,
            status=draft.status,
            team_count=draft.team_count,
            rounds=draft.rounds,
            current_pick_number=next_pick,
            current_round=current_round,
            current_pick_in_round=current_pick_in_round,
            started_at=draft.started_at,
            completed_at=draft.completed_at,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    async def _board_response(self, draft: DraftSession) -> DraftBoardResponse:
        draft_read = await self._draft_read(draft)
        on_clock_team = None
        if draft_read.current_pick_number is not None and draft.status == "in_progress":
            _, _, draft_position = snake_pick_details(
                draft_read.current_pick_number,
                draft.team_count,
            )
            team = next(
                (item for item in draft.teams if item.draft_position == draft_position),
                None,
            )
            on_clock_team = FantasyTeamRead.model_validate(team) if team else None
        picks = await self._pick_reads(draft, draft.picks)
        return DraftBoardResponse(
            draft=draft_read,
            on_clock_team=on_clock_team,
            teams=[FantasyTeamRead.model_validate(team) for team in draft.teams],
            picks=picks,
            recent_picks=list(reversed(picks[-5:])),
        )

    async def _pick_reads(
        self,
        draft: DraftSession,
        picks: list[DraftPick],
    ) -> list[DraftPickRead]:
        league = await self.repository.get_singleton_league()
        configured_slots = self._configured_draft_slots(league) if league else []
        reads = []
        for pick in sorted(picks, key=lambda item: item.overall_pick):
            positions = await self.repository.get_player_eligibilities(pick.player_id)
            reads.append(
                DraftPickRead(
                    id=pick.id,
                    draft_session_id=pick.draft_session_id,
                    fantasy_team_id=pick.fantasy_team_id,
                    player_id=pick.player_id,
                    player_name=pick.player.full_name,
                    team=pick.player.team,
                    primary_position=pick.player.primary_position,
                    eligible_positions=positions,
                    compatible_roster_slots=compatible_roster_slots(
                        positions,
                        configured_slots,
                    ),
                    fantasy_team_name=pick.fantasy_team.name,
                    round_number=pick.round_number,
                    pick_in_round=pick.pick_in_round,
                    overall_pick=pick.overall_pick,
                    created_at=pick.created_at,
                )
            )
        return reads

    async def _available_player_reads(
        self,
        draft: DraftSession,
        rows: list[tuple[Player, PlayerProjection]],
    ) -> list[AvailablePlayerRead]:
        league = await self.repository.get_singleton_league()
        scorer = FantasyScorer(league.scoring_rules) if league else None
        configured_slots = self._configured_draft_slots(league) if league else []
        items = []
        for player, projection in rows:
            positions = await self.repository.get_player_eligibilities(player.id)
            fantasy_points = (
                scorer.fantasy_points_per_game(projection) if scorer else 0
            )
            items.append(
                AvailablePlayerRead(
                    player_id=player.id,
                    full_name=player.full_name,
                    team=player.team,
                    primary_position=player.primary_position,
                    eligible_positions=positions,
                    compatible_roster_slots=compatible_roster_slots(
                        positions,
                        configured_slots,
                    ),
                    fantasy_points_per_game=fantasy_points,
                    projected_fantasy_points=fantasy_points * projection.games,
                )
            )
        return items

    def _configured_draft_slots(self, league) -> list[str]:
        return [
            slot.slot_key
            for slot in sorted(league.roster_slots, key=lambda item: item.sort_order)
            if slot.count > 0 and slot.slot_key != "IR"
        ]
