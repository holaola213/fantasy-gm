from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.draft_assistant.availability import AvailabilityOutlook
from app.draft_assistant.roster_assignment import (
    BenchAssignment,
    RosterAssignmentResult,
    RosterPlayer,
    SlotInstance,
    assign_roster,
    matching_open_slots,
)
from app.draft_assistant.scarcity import PositionScarcity
from app.draft_assistant.schemas import (
    AssistantReasonRead,
    DraftRecommendationRead,
    RecommendationRosterFitRead,
    RecommendationScoreBreakdownRead,
    SlotInstanceRead,
)
from app.draft_assistant.value_gaps import ValueDrop
from app.drafts.compatibility import BASE_POSITION_ORDER
from app.valuations.schemas import PlayerValuationRead

RECOMMENDATION_CLOSE_VALUE_WINDOW = Decimal("10.00")
RECOMMENDATION_MIN_CANDIDATES = 10
RECOMMENDATION_RETURN_LIMIT = 5
SIGNIFICANT_REACH_WARNING_THRESHOLD = Decimal("20.00")

MAX_VALUE_SCORE = Decimal("100.00")
VALUE_SCORE_RANGE = Decimal("20.00")
SCORE_QUANT = Decimal("0.01")

RESTRICTIVE_SLOT_KEYS = {"PG", "SG", "SF", "PF", "C"}
FLEX_SLOT_KEYS = {"G", "F", "UTIL"}
ABSOLUTE_WORDS = {"guaranteed", "must draft", "certain", "safe", "definitely", "will not return"}


@dataclass(frozen=True)
class RecommendationInput:
    available: list[PlayerValuationRead]
    current_roster_players: list[RosterPlayer]
    current_assignment: RosterAssignmentResult
    roster_slot_counts: dict[str, int]
    availability_by_player_id: dict[int, AvailabilityOutlook]
    scarcity_by_position: dict[str, PositionScarcity]
    value_drop: ValueDrop | None
    is_user_on_clock: bool


@dataclass(frozen=True)
class CandidateRosterFit:
    assignment_type: str
    assigned_slot: SlotInstance | None
    eligible_roster_slots: list[SlotInstance]
    fills_open_slot: bool
    improves_active_lineup: bool
    useful_flexibility: bool


@dataclass(frozen=True)
class ScoreBreakdown:
    value_proximity_score: Decimal
    roster_fit_score: Decimal
    scarcity_score: Decimal
    availability_score: Decimal
    value_drop_score: Decimal
    flexibility_score: Decimal

    @property
    def total_score(self) -> Decimal:
        return quantize_score(
            self.value_proximity_score
            + self.roster_fit_score
            + self.scarcity_score
            + self.availability_score
            + self.value_drop_score
            + self.flexibility_score
        )


@dataclass(frozen=True)
class RecommendationCandidate:
    player: PlayerValuationRead
    available_rank: int
    context: str
    roster_fit: CandidateRosterFit
    scarcity_position: str | None
    scarcity: PositionScarcity | None
    availability: AvailabilityOutlook | None
    score_breakdown: ScoreBreakdown | None
    reasons: list[AssistantReasonRead]
    warnings: list[AssistantReasonRead]
    explanation: str


def recommend_players(input: RecommendationInput) -> list[DraftRecommendationRead]:
    ranked_available = [
        (rank, item)
        for rank, item in enumerate(input.available, start=1)
        if item.overall_vor is not None and item.eligible_positions
    ]
    if not ranked_available:
        return []

    best_vor = ranked_available[0][1].overall_vor
    reorderable = [
        (rank, item)
        for rank, item in ranked_available
        if best_vor - item.overall_vor <= RECOMMENDATION_CLOSE_VALUE_WINDOW
    ]
    reorderable_ids = {item.player_id for _, item in reorderable}
    fallback = [
        (rank, item)
        for rank, item in enumerate(
            input.available[:RECOMMENDATION_MIN_CANDIDATES],
            start=1,
        )
        if item.overall_vor is not None
        and item.eligible_positions
        and item.player_id not in reorderable_ids
    ]

    scored_reorderable = [
        _candidate(
            input=input,
            best_vor=best_vor,
            available_rank=available_rank,
            player=player,
            context="CLOSE_VALUE",
        )
        for available_rank, player in reorderable
    ]
    scored_reorderable.sort(key=_reorderable_sort_key)
    fallback_candidates = [
        _candidate(
            input=input,
            best_vor=best_vor,
            available_rank=available_rank,
            player=player,
            context="FALLBACK_VALUE",
        )
        for available_rank, player in fallback
    ]
    final = [*scored_reorderable, *fallback_candidates][
        :RECOMMENDATION_RETURN_LIMIT
    ]
    return [_read(candidate, rank) for rank, candidate in enumerate(final, start=1)]


def value_proximity_score(*, best_vor: Decimal, candidate_vor: Decimal) -> Decimal:
    value_gap = best_vor - candidate_vor
    score = MAX_VALUE_SCORE - (
        value_gap / RECOMMENDATION_CLOSE_VALUE_WINDOW * VALUE_SCORE_RANGE
    )
    return quantize_score(score)


def quantize_score(value: Decimal) -> Decimal:
    return value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _candidate(
    *,
    input: RecommendationInput,
    best_vor: Decimal,
    available_rank: int,
    player: PlayerValuationRead,
    context: str,
) -> RecommendationCandidate:
    roster_fit = _roster_fit(input=input, player=player)
    availability = input.availability_by_player_id.get(player.player_id)
    scarcity_position = _scarcity_position(
        player=player,
        roster_fit=roster_fit,
        scarcity_by_position=input.scarcity_by_position,
    )
    scarcity = (
        input.scarcity_by_position.get(scarcity_position)
        if scarcity_position
        else None
    )
    reasons: list[AssistantReasonRead] = []
    warnings: list[AssistantReasonRead] = []
    score_breakdown = (
        _score_breakdown(
            best_vor=best_vor,
            player=player,
            roster_fit=roster_fit,
            scarcity=scarcity,
            availability=availability,
            value_drop=input.value_drop,
            available_rank=available_rank,
            is_user_on_clock=input.is_user_on_clock,
        )
        if context == "CLOSE_VALUE"
        else None
    )
    _add_value_reasons(
        reasons=reasons,
        warnings=warnings,
        best_vor=best_vor,
        player=player,
        context=context,
    )
    _add_roster_reasons(reasons=reasons, warnings=warnings, roster_fit=roster_fit)
    _add_scarcity_reasons(reasons=reasons, warnings=warnings, scarcity=scarcity)
    _add_availability_reasons(
        reasons=reasons,
        warnings=warnings,
        availability=availability,
        is_user_on_clock=input.is_user_on_clock,
    )
    _add_value_drop_reason(
        reasons=reasons,
        value_drop=input.value_drop,
        available_rank=available_rank,
    )
    explanation = _explanation(
        player=player,
        context=context,
        roster_fit=roster_fit,
        reasons=reasons,
        warnings=warnings,
    )
    return RecommendationCandidate(
        player=player,
        available_rank=available_rank,
        context=context,
        roster_fit=roster_fit,
        scarcity_position=scarcity_position,
        scarcity=scarcity,
        availability=availability,
        score_breakdown=score_breakdown,
        reasons=reasons,
        warnings=warnings,
        explanation=explanation,
    )


def _score_breakdown(
    *,
    best_vor: Decimal,
    player: PlayerValuationRead,
    roster_fit: CandidateRosterFit,
    scarcity: PositionScarcity | None,
    availability: AvailabilityOutlook | None,
    value_drop: ValueDrop | None,
    available_rank: int,
    is_user_on_clock: bool,
) -> ScoreBreakdown:
    return ScoreBreakdown(
        value_proximity_score=value_proximity_score(
            best_vor=best_vor,
            candidate_vor=player.overall_vor or Decimal("0"),
        ),
        roster_fit_score=_roster_fit_score(roster_fit),
        scarcity_score=_scarcity_score(scarcity),
        availability_score=_availability_score(
            availability=availability,
            is_user_on_clock=is_user_on_clock,
        ),
        value_drop_score=_value_drop_score(
            value_drop=value_drop,
            available_rank=available_rank,
        ),
        flexibility_score=Decimal("1.00") if roster_fit.useful_flexibility else Decimal("0.00"),
    )


def _roster_fit(input: RecommendationInput, player: PlayerValuationRead) -> CandidateRosterFit:
    current_active_points = _active_points(input.current_assignment)
    candidate = RosterPlayer(
        draft_pick_id=0,
        player_id=player.player_id,
        player_name=player.player_name,
        eligible_positions=tuple(player.eligible_positions),
        projected_fantasy_points=player.projected_fantasy_points,
        overall_pick=999999,
    )
    result = assign_roster(
        players=[*input.current_roster_players, candidate],
        roster_slot_counts=input.roster_slot_counts,
    )
    active_assignment = next(
        (
            assignment
            for assignment in result.active_assignments
            if assignment.player.player_id == player.player_id
        ),
        None,
    )
    if active_assignment is not None:
        assigned_slot = active_assignment.slot
        assignment_type = "active"
    else:
        bench_assignment = _bench_assignment(result, player.player_id)
        if bench_assignment is not None:
            assigned_slot = SlotInstance(slot="BE", slot_index=bench_assignment.bench_index)
            assignment_type = "bench"
        else:
            assigned_slot = None
            assignment_type = "unassigned"

    matching_slots = matching_open_slots(
        eligible_positions=player.eligible_positions,
        open_slots=input.current_assignment.unfilled_slots,
    )
    fills_open_slot = (
        assigned_slot is not None
        and any(
            slot.slot == assigned_slot.slot and slot.slot_index == assigned_slot.slot_index
            for slot in matching_slots
        )
    )
    improves_active_lineup = (
        assignment_type == "active" and _active_points(result) > current_active_points
    )
    active_assignment_paths = matching_open_slots(
        eligible_positions=player.eligible_positions,
        open_slots=input.current_assignment.active_slots,
    )
    eligible_base_positions = {
        position for position in player.eligible_positions if position in BASE_POSITION_ORDER
    }
    useful_flexibility = (
        assignment_type == "active"
        and len(eligible_base_positions) >= 2
        and len({slot.slot for slot in active_assignment_paths}) >= 2
    )
    return CandidateRosterFit(
        assignment_type=assignment_type,
        assigned_slot=assigned_slot,
        eligible_roster_slots=matching_slots,
        fills_open_slot=fills_open_slot,
        improves_active_lineup=improves_active_lineup,
        useful_flexibility=useful_flexibility,
    )


def _bench_assignment(
    result: RosterAssignmentResult,
    player_id: int,
) -> BenchAssignment | None:
    return next(
        (
            assignment
            for assignment in result.bench_assignments
            if assignment.player.player_id == player_id
        ),
        None,
    )


def _active_points(result: RosterAssignmentResult) -> Decimal:
    return sum(
        (
            assignment.player.projected_fantasy_points or Decimal("0")
            for assignment in result.active_assignments
        ),
        Decimal("0"),
    )


def _roster_fit_score(roster_fit: CandidateRosterFit) -> Decimal:
    if roster_fit.assignment_type == "active" and roster_fit.assigned_slot:
        if roster_fit.assigned_slot.slot in RESTRICTIVE_SLOT_KEYS:
            score = Decimal("5.00")
        elif roster_fit.assigned_slot.slot in FLEX_SLOT_KEYS:
            score = Decimal("3.00")
        else:
            score = Decimal("0.00")
    elif roster_fit.assignment_type == "bench":
        score = Decimal("-2.00")
    else:
        score = Decimal("-5.00")
    if roster_fit.improves_active_lineup:
        score += Decimal("2.00")
    return quantize_score(score)


def _scarcity_score(scarcity: PositionScarcity | None) -> Decimal:
    if scarcity is None:
        return Decimal("0.00")
    if scarcity.severity == "HIGH":
        return Decimal("3.00")
    if scarcity.severity == "MEDIUM":
        return Decimal("1.50")
    return Decimal("0.00")


def _availability_score(
    *,
    availability: AvailabilityOutlook | None,
    is_user_on_clock: bool,
) -> Decimal:
    if is_user_on_clock or availability is None:
        return Decimal("0.00")
    if availability.outlook == "UNLIKELY_TO_RETURN":
        return Decimal("3.00")
    if availability.outlook == "AT_RISK":
        return Decimal("1.50")
    return Decimal("0.00")


def _value_drop_score(
    *,
    value_drop: ValueDrop | None,
    available_rank: int,
) -> Decimal:
    if value_drop and available_rank <= value_drop.drop_after_available_rank:
        return Decimal("1.50")
    return Decimal("0.00")


def _scarcity_position(
    *,
    player: PlayerValuationRead,
    roster_fit: CandidateRosterFit,
    scarcity_by_position: dict[str, PositionScarcity],
) -> str | None:
    if (
        roster_fit.assigned_slot
        and roster_fit.assigned_slot.slot in RESTRICTIVE_SLOT_KEYS
        and roster_fit.assigned_slot.slot in player.eligible_positions
    ):
        return roster_fit.assigned_slot.slot
    if (
        player.best_value_position
        and player.best_value_position in player.eligible_positions
        and player.best_value_position in scarcity_by_position
    ):
        return player.best_value_position
    eligible = [
        position
        for position in BASE_POSITION_ORDER
        if position in player.eligible_positions and position in scarcity_by_position
    ]
    if not eligible:
        return None
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(
        eligible,
        key=lambda position: (
            severity_rank[scarcity_by_position[position].severity],
            BASE_POSITION_ORDER.index(position),
        ),
    )[0]


def _add_value_reasons(
    *,
    reasons: list[AssistantReasonRead],
    warnings: list[AssistantReasonRead],
    best_vor: Decimal,
    player: PlayerValuationRead,
    context: str,
) -> None:
    if context == "CLOSE_VALUE" and player.overall_vor == best_vor:
        reasons.append(AssistantReasonRead(code="BEST_AVAILABLE_VALUE"))
    elif context == "CLOSE_VALUE":
        reasons.append(AssistantReasonRead(code="STRONG_VALUE"))
    if best_vor - (player.overall_vor or Decimal("0")) >= SIGNIFICANT_REACH_WARNING_THRESHOLD:
        warnings.append(AssistantReasonRead(code="SIGNIFICANT_VALUE_REACH"))


def _add_roster_reasons(
    *,
    reasons: list[AssistantReasonRead],
    warnings: list[AssistantReasonRead],
    roster_fit: CandidateRosterFit,
) -> None:
    if roster_fit.assignment_type == "active" and roster_fit.assigned_slot:
        slot_read = _slot_read(roster_fit.assigned_slot)
        if roster_fit.assigned_slot.slot in RESTRICTIVE_SLOT_KEYS:
            reasons.append(
                AssistantReasonRead(
                    code="FILLS_RESTRICTIVE_STARTER_SLOT",
                    position=roster_fit.assigned_slot.slot,
                    slots=[slot_read],
                )
            )
        elif roster_fit.assigned_slot.slot in FLEX_SLOT_KEYS:
            reasons.append(
                AssistantReasonRead(code="FILLS_FLEX_SLOT", slots=[slot_read])
            )
    elif roster_fit.assignment_type == "bench":
        warnings.append(AssistantReasonRead(code="BENCH_ONLY_FIT"))
    else:
        warnings.append(AssistantReasonRead(code="MISSING_CONTEXT"))
    if roster_fit.improves_active_lineup:
        reasons.append(AssistantReasonRead(code="IMPROVES_ACTIVE_LINEUP"))
    if roster_fit.useful_flexibility:
        reasons.append(AssistantReasonRead(code="MULTI_POSITION_FLEXIBILITY"))


def _add_scarcity_reasons(
    *,
    reasons: list[AssistantReasonRead],
    warnings: list[AssistantReasonRead],
    scarcity: PositionScarcity | None,
) -> None:
    if scarcity is None:
        return
    if scarcity.severity == "HIGH":
        reasons.append(
            AssistantReasonRead(code="LIMITED_POSITION_DEPTH", position=scarcity.position)
        )
    elif scarcity.severity == "MEDIUM":
        reasons.append(
            AssistantReasonRead(code="POSITION_VALUE_DROP", position=scarcity.position)
        )
    elif scarcity.severity == "LOW":
        warnings.append(
            AssistantReasonRead(code="POSITION_ALREADY_DEEP", position=scarcity.position)
        )


def _add_availability_reasons(
    *,
    reasons: list[AssistantReasonRead],
    warnings: list[AssistantReasonRead],
    availability: AvailabilityOutlook | None,
    is_user_on_clock: bool,
) -> None:
    if is_user_on_clock or availability is None:
        return
    if "NO_FUTURE_USER_PICK" in availability.reason_codes:
        return
    if availability.outlook == "UNLIKELY_TO_RETURN":
        reasons.append(AssistantReasonRead(code="UNLIKELY_TO_RETURN"))
    elif availability.outlook == "AT_RISK":
        reasons.append(AssistantReasonRead(code="AT_RISK_BEFORE_NEXT_PICK"))
    elif availability.outlook == "COULD_RETURN":
        warnings.append(AssistantReasonRead(code="COULD_RETURN_LATER"))


def _add_value_drop_reason(
    *,
    reasons: list[AssistantReasonRead],
    value_drop: ValueDrop | None,
    available_rank: int,
) -> None:
    if value_drop and available_rank <= value_drop.drop_after_available_rank:
        reasons.append(AssistantReasonRead(code="BEFORE_MEANINGFUL_VALUE_DROP"))


def _explanation(
    *,
    player: PlayerValuationRead,
    context: str,
    roster_fit: CandidateRosterFit,
    reasons: list[AssistantReasonRead],
    warnings: list[AssistantReasonRead],
) -> str:
    if context == "FALLBACK_VALUE":
        prefix = "A value-based alternative"
    elif any(reason.code == "BEST_AVAILABLE_VALUE" for reason in reasons):
        prefix = "Strong overall value"
    else:
        prefix = "Close-value option"

    clauses = []
    if roster_fit.assignment_type == "active" and roster_fit.assigned_slot:
        if roster_fit.assigned_slot.slot in RESTRICTIVE_SLOT_KEYS:
            if roster_fit.fills_open_slot:
                clauses.append(f"fills an open {roster_fit.assigned_slot.slot} slot")
            else:
                clauses.append(
                    f"projects into the starting lineup at {roster_fit.assigned_slot.slot}"
                )
        elif roster_fit.assigned_slot.slot in FLEX_SLOT_KEYS:
            if roster_fit.fills_open_slot:
                clauses.append("may fit an open flex slot")
            else:
                clauses.append("projects into a flex lineup slot")
    elif any(warning.code == "BENCH_ONLY_FIT" for warning in warnings):
        clauses.append("may project to your bench")

    if any(reason.code == "UNLIKELY_TO_RETURN" for reason in reasons):
        clauses.append("may not remain available until your next pick")
    elif any(reason.code == "AT_RISK_BEFORE_NEXT_PICK" for reason in reasons):
        clauses.append("is at risk before your next pick")
    elif any(warning.code == "COULD_RETURN_LATER" for warning in warnings):
        clauses.append("could still return later")

    if not clauses and player.overall_vor is not None:
        clauses.append("keeps value near the top of the board")

    sentence = f"{prefix} that {' and '.join(clauses)}."
    lowered = sentence.casefold()
    if any(word in lowered for word in ABSOLUTE_WORDS):
        raise ValueError("recommendation explanation used absolute language")
    return sentence


def _reorderable_sort_key(candidate: RecommendationCandidate) -> tuple:
    breakdown = candidate.score_breakdown
    assert breakdown is not None
    return (
        -breakdown.total_score,
        -breakdown.value_proximity_score,
        -(candidate.player.overall_vor or Decimal("-999999999")),
        -candidate.player.projected_fantasy_points,
        candidate.player.overall_rank is None,
        candidate.player.overall_rank or 999999999,
        candidate.player.player_name.casefold(),
        candidate.player.player_id,
    )


def _read(candidate: RecommendationCandidate, rank: int) -> DraftRecommendationRead:
    return DraftRecommendationRead(
        recommendation_rank=rank,
        recommendation_context=candidate.context,
        player_id=candidate.player.player_id,
        player_name=candidate.player.player_name,
        team=candidate.player.team,
        primary_position=candidate.player.primary_position,
        eligible_positions=candidate.player.eligible_positions,
        overall_rank=candidate.player.overall_rank,
        overall_vor=candidate.player.overall_vor or Decimal("0"),
        projected_fantasy_points=candidate.player.projected_fantasy_points,
        projected_roster_assignment=RecommendationRosterFitRead(
            assignment_type=candidate.roster_fit.assignment_type,
            assigned_slot=(
                candidate.roster_fit.assigned_slot.slot
                if candidate.roster_fit.assigned_slot
                else None
            ),
            slot_index=(
                candidate.roster_fit.assigned_slot.slot_index
                if candidate.roster_fit.assigned_slot
                else None
            ),
            eligible_roster_slots=[
                _slot_read(slot) for slot in candidate.roster_fit.eligible_roster_slots
            ],
        ),
        availability_outlook=(
            candidate.availability.outlook if candidate.availability else None
        ),
        scarcity_position=candidate.scarcity_position,
        scarcity_severity=candidate.scarcity.severity if candidate.scarcity else None,
        explanation=candidate.explanation,
        reasons=candidate.reasons,
        warnings=candidate.warnings,
        score_breakdown=(
            RecommendationScoreBreakdownRead(
                value_proximity_score=candidate.score_breakdown.value_proximity_score,
                roster_fit_score=candidate.score_breakdown.roster_fit_score,
                scarcity_score=candidate.score_breakdown.scarcity_score,
                availability_score=candidate.score_breakdown.availability_score,
                value_drop_score=candidate.score_breakdown.value_drop_score,
                flexibility_score=candidate.score_breakdown.flexibility_score,
                total_score=candidate.score_breakdown.total_score,
            )
            if candidate.score_breakdown
            else None
        ),
    )


def _slot_read(slot: SlotInstance) -> SlotInstanceRead:
    return SlotInstanceRead(slot=slot.slot, slot_index=slot.slot_index)
