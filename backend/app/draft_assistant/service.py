from __future__ import annotations

from decimal import Decimal

from app.draft_assistant.repository import DraftAssistantRepository
from app.draft_assistant.roster_assignment import (
    ACTIVE_SLOT_KEYS,
    RESTRICTIVE_SLOT_KEYS,
    SlotInstance,
    UnsupportedRosterSlotError,
    assign_roster,
    matching_open_slots,
)
from app.draft_assistant.schemas import (
    AssistantPlayerRead,
    AssistantReasonRead,
    AssistantTeamRead,
    BenchAssignmentRead,
    BestByPositionRead,
    DraftAssistantResponse,
    RosterAssignmentRead,
    RosterSummaryRead,
    SlotInstanceRead,
    UnassignedPlayerRead,
    UserTeamRead,
)
from app.drafts.compatibility import snake_pick_details
from app.drafts.model import DraftPick, DraftSession, FantasyTeam
from app.valuations.repository import ValuationRepository
from app.valuations.schemas import PlayerValuationRead, PositionValueRead
from app.valuations.service import (
    ActiveProjectionSetRequiredError,
    LeagueConfigurationRequiredError,
    ProjectionSetNotFoundError,
    ValuationService,
)

BASE_POSITION_ORDER = ["PG", "SG", "SF", "PF", "C"]


class ActiveDraftRequiredError(Exception):
    pass


class UserFantasyTeamRequiredError(Exception):
    pass


class DraftAssistantService:
    def __init__(self, repository: DraftAssistantRepository) -> None:
        self.repository = repository

    async def get_assistant(
        self,
        *,
        limit_per_section: int,
        include_assignments: bool,
    ) -> DraftAssistantResponse:
        draft = await self.repository.get_current_in_progress_draft()
        if draft is None:
            raise ActiveDraftRequiredError
        user_team = self._user_team(draft)
        league = await self.repository.get_singleton_league()
        if league is None:
            raise LeagueConfigurationRequiredError

        valuations = await self._valuation_universe(draft)
        valuations_by_player_id = {item.player_id: item for item in valuations}
        drafted_player_ids = {pick.player_id for pick in draft.picks}
        available = [
            item for item in valuations if item.player_id not in drafted_player_ids
        ]
        available = sorted(available, key=_best_available_key)

        roster_summary = await self._roster_summary(
            draft=draft,
            league=league,
            user_team=user_team,
            valuations_by_player_id=valuations_by_player_id,
            include_assignments=include_assignments,
        )
        open_slots = [
            SlotInstance(slot=item.slot, slot_index=item.slot_index)
            for item in roster_summary.unfilled_slots
        ]
        current_round, _, draft_position = snake_pick_details(
            self._current_overall_pick(draft),
            draft.team_count,
        )
        on_clock_team = next(
            (team for team in draft.teams if team.draft_position == draft_position),
            None,
        )
        return DraftAssistantResponse(
            draft_id=draft.id,
            status="in_progress",
            current_round=current_round,
            current_overall_pick=self._current_overall_pick(draft),
            on_clock_team=self._team_read(on_clock_team) if on_clock_team else None,
            is_user_on_clock=(
                on_clock_team is not None and on_clock_team.id == user_team.id
            ),
            user_team=UserTeamRead(
                fantasy_team_id=user_team.id,
                name=user_team.name,
                draft_position=user_team.draft_position,
                players_drafted=len(self._user_picks(draft, user_team)),
                roster_spots_remaining=roster_summary.roster_spots_remaining,
            ),
            roster_summary=roster_summary,
            best_available=[
                self._assistant_item(
                    valuation=item,
                    reasons=[AssistantReasonRead(code="BEST_AVAILABLE")],
                    open_slots=open_slots,
                )
                for item in available[:limit_per_section]
            ],
            best_by_position=self._best_by_position(
                available=available,
                open_slots=open_slots,
                limit_per_section=limit_per_section,
            ),
            roster_fit_options=self._roster_fits(
                available=available,
                open_slots=open_slots,
                limit_per_section=limit_per_section,
            ),
        )

    async def _valuation_universe(self, draft: DraftSession) -> list[PlayerValuationRead]:
        service = ValuationService(ValuationRepository(self.repository.session))
        items, _, _ = await service.list_valuations(
            projection_set_id=draft.projection_set_id,
            available_only=False,
            search=None,
            team=None,
            position=None,
            sort="overall_rank",
            direction="asc",
            limit=10000,
            offset=0,
        )
        return items

    async def _roster_summary(
        self,
        *,
        draft: DraftSession,
        league,
        user_team: FantasyTeam,
        valuations_by_player_id: dict[int, PlayerValuationRead],
        include_assignments: bool,
    ) -> RosterSummaryRead:
        user_picks = self._user_picks(draft, user_team)
        player_ids = [pick.player_id for pick in user_picks]
        eligibilities = await self.repository.get_eligibilities_by_player_ids(player_ids)
        players = [
            self._roster_player(
                pick=pick,
                eligible_positions=eligibilities.get(pick.player_id, []),
                valuation=valuations_by_player_id.get(pick.player_id),
            )
            for pick in user_picks
        ]
        result = assign_roster(
            players=players,
            roster_slot_counts={slot.slot_key: slot.count for slot in league.roster_slots},
        )
        active_filled = len(result.active_assignments)
        bench_filled = len(result.bench_assignments)
        roster_spots_remaining = max(
            result.draftable_roster_capacity - len(user_picks), 0
        )
        return RosterSummaryRead(
            active_slots_total=len(result.active_slots),
            active_slots_filled=active_filled,
            active_slots_unfilled=len(result.unfilled_slots),
            bench_slots_total=result.bench_slots_total,
            bench_slots_filled=bench_filled,
            bench_slots_remaining=max(result.bench_slots_total - bench_filled, 0),
            draftable_roster_capacity=result.draftable_roster_capacity,
            players_drafted=len(user_picks),
            roster_spots_remaining=roster_spots_remaining,
            assignments=[
                RosterAssignmentRead(
                    draft_pick_id=assignment.player.draft_pick_id,
                    player_id=assignment.player.player_id,
                    player_name=assignment.player.player_name,
                    eligible_positions=list(assignment.player.eligible_positions),
                    assigned_slot=assignment.slot.slot,
                    slot_index=assignment.slot.slot_index,
                    projected_fantasy_points=assignment.player.projected_fantasy_points,
                )
                for assignment in result.active_assignments
            ]
            if include_assignments
            else [],
            bench_assignments=[
                BenchAssignmentRead(
                    draft_pick_id=assignment.player.draft_pick_id,
                    player_id=assignment.player.player_id,
                    player_name=assignment.player.player_name,
                    eligible_positions=list(assignment.player.eligible_positions),
                    bench_index=assignment.bench_index,
                    projected_fantasy_points=assignment.player.projected_fantasy_points,
                )
                for assignment in result.bench_assignments
            ]
            if include_assignments
            else [],
            unfilled_slots=[self._slot_read(slot) for slot in result.unfilled_slots],
            unassigned_players=[
                UnassignedPlayerRead(
                    draft_pick_id=item.player.draft_pick_id,
                    player_id=item.player.player_id,
                    player_name=item.player.player_name,
                    eligible_positions=list(item.player.eligible_positions),
                    reason=item.reason,
                    projected_fantasy_points=item.player.projected_fantasy_points,
                )
                for item in result.unassigned_players
            ]
            if include_assignments
            else [],
        )

    def _best_by_position(
        self,
        *,
        available: list[PlayerValuationRead],
        open_slots: list[SlotInstance],
        limit_per_section: int,
    ) -> list[BestByPositionRead]:
        sections = []
        for position in BASE_POSITION_ORDER:
            rows = [
                (item, value)
                for item in available
                for value in item.position_values
                if value.position == position
            ]
            rows.sort(key=lambda pair: _position_key(pair[0], pair[1]))
            sections.append(
                BestByPositionRead(
                    position=position,
                    items=[
                        self._assistant_item(
                            valuation=item,
                            reasons=[
                                AssistantReasonRead(
                                    code="BEST_AT_POSITION",
                                    position=position,
                                )
                            ],
                            open_slots=open_slots,
                            position_value=value,
                        )
                        for item, value in rows[:limit_per_section]
                    ],
                )
            )
        return sections

    def _roster_fits(
        self,
        *,
        available: list[PlayerValuationRead],
        open_slots: list[SlotInstance],
        limit_per_section: int,
    ) -> list[AssistantPlayerRead]:
        if not open_slots:
            return []
        matches = [
            item
            for item in available
            if matching_open_slots(
                eligible_positions=item.eligible_positions,
                open_slots=open_slots,
            )
        ]
        return [
            self._assistant_item(
                valuation=item,
                reasons=self._fit_reasons(item, open_slots),
                open_slots=open_slots,
            )
            for item in matches[:limit_per_section]
        ]

    def _assistant_item(
        self,
        *,
        valuation: PlayerValuationRead,
        reasons: list[AssistantReasonRead],
        open_slots: list[SlotInstance],
        position_value: PositionValueRead | None = None,
    ) -> AssistantPlayerRead:
        matches = matching_open_slots(
            eligible_positions=valuation.eligible_positions,
            open_slots=open_slots,
        )
        return AssistantPlayerRead(
            player_id=valuation.player_id,
            player_name=valuation.player_name,
            team=valuation.team,
            primary_position=valuation.primary_position,
            eligible_positions=valuation.eligible_positions,
            overall_rank=valuation.overall_rank,
            overall_vor=valuation.overall_vor,
            best_value_position=valuation.best_value_position,
            fantasy_points_per_game=valuation.fantasy_points_per_game,
            projected_fantasy_points=valuation.projected_fantasy_points,
            position=position_value.position if position_value else None,
            position_rank=position_value.position_rank if position_value else None,
            position_vor=position_value.vor if position_value else None,
            matching_open_slots=[self._slot_read(slot) for slot in matches],
            reasons=reasons,
        )

    def _fit_reasons(
        self,
        valuation: PlayerValuationRead,
        open_slots: list[SlotInstance],
    ) -> list[AssistantReasonRead]:
        matches = matching_open_slots(
            eligible_positions=valuation.eligible_positions,
            open_slots=open_slots,
        )
        reasons = [
            AssistantReasonRead(
                code="FILLS_OPEN_SLOT",
                slots=[self._slot_read(slot) for slot in matches],
            )
        ]
        restrictive = [slot for slot in matches if slot.slot in RESTRICTIVE_SLOT_KEYS]
        if restrictive:
            reasons.append(
                AssistantReasonRead(
                    code="FILLS_RESTRICTIVE_SLOT",
                    slots=[self._slot_read(slot) for slot in restrictive],
                )
            )
        if len(matches) >= 2:
            reasons.append(
                AssistantReasonRead(
                    code="MULTI_SLOT_FLEXIBILITY",
                    slots=[self._slot_read(slot) for slot in matches],
                )
            )
        return reasons

    def _roster_player(self, *, pick: DraftPick, eligible_positions, valuation):
        from app.draft_assistant.roster_assignment import RosterPlayer

        return RosterPlayer(
            draft_pick_id=pick.id,
            player_id=pick.player_id,
            player_name=pick.player.full_name,
            eligible_positions=tuple(eligible_positions),
            projected_fantasy_points=(
                valuation.projected_fantasy_points if valuation else None
            ),
            overall_pick=pick.overall_pick,
        )

    def _user_team(self, draft: DraftSession) -> FantasyTeam:
        user_teams = [team for team in draft.teams if team.is_user_team]
        if len(user_teams) != 1:
            raise UserFantasyTeamRequiredError
        return user_teams[0]

    def _user_picks(self, draft: DraftSession, user_team: FantasyTeam) -> list[DraftPick]:
        return sorted(
            [pick for pick in draft.picks if pick.fantasy_team_id == user_team.id],
            key=lambda pick: pick.overall_pick,
        )

    def _current_overall_pick(self, draft: DraftSession) -> int:
        return len(draft.picks) + 1

    def _team_read(self, team: FantasyTeam) -> AssistantTeamRead:
        return AssistantTeamRead(
            fantasy_team_id=team.id,
            name=team.name,
            draft_position=team.draft_position,
        )

    def _slot_read(self, slot: SlotInstance) -> SlotInstanceRead:
        return SlotInstanceRead(slot=slot.slot, slot_index=slot.slot_index)


def _best_available_key(item: PlayerValuationRead):
    return (
        item.overall_rank is None,
        item.overall_rank or 999999999,
        -item.projected_fantasy_points,
        item.player_name.casefold(),
        item.player_id,
    )


def _position_key(item: PlayerValuationRead, value: PositionValueRead):
    return (
        value.position_rank,
        item.overall_rank is None,
        item.overall_rank or 999999999,
        -item.projected_fantasy_points,
        item.player_name.casefold(),
        item.player_id,
    )
