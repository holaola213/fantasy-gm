from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.drafts.schemas import PositionKey

ReasonCode = Literal[
    "BEST_AVAILABLE",
    "BEST_AT_POSITION",
    "BEYOND_NEXT_PICK_WINDOW",
    "FILLS_OPEN_SLOT",
    "FILLS_RESTRICTIVE_SLOT",
    "INSIDE_NEXT_PICK_WINDOW",
    "LARGE_VALUE_DROP",
    "LIMITED_POSITION_DEPTH",
    "MULTI_SLOT_FLEXIBILITY",
    "NEAR_NEXT_PICK_WINDOW",
    "NO_FUTURE_USER_PICK",
    "POSITION_DEPTH_AVAILABLE",
    "POSITION_VALUE_DROP",
    "USER_ON_CLOCK",
]
AvailabilityOutlook = Literal["UNLIKELY_TO_RETURN", "AT_RISK", "COULD_RETURN"]
ScarcitySeverity = Literal["HIGH", "MEDIUM", "LOW"]
SlotKey = Literal["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "BE"]


class DecimalStringMixin(BaseModel):
    @field_serializer(
        "projected_fantasy_points",
        "fantasy_points_per_game",
        "overall_vor",
        "position_vor",
        "top_position_vor",
        "cutoff_position_vor",
        "projected_vor_drop",
        "meaningful_value_drop",
        "before_overall_vor",
        "after_overall_vor",
        "gap",
        check_fields=False,
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value.quantize(Decimal("0.01")))


class SlotInstanceRead(BaseModel):
    slot: SlotKey
    slot_index: int = Field(ge=1)


class AssistantTeamRead(BaseModel):
    fantasy_team_id: int
    name: str
    draft_position: int


class UserTeamRead(AssistantTeamRead):
    players_drafted: int = Field(ge=0)
    roster_spots_remaining: int = Field(ge=0)


class RosterAssignmentRead(DecimalStringMixin):
    draft_pick_id: int
    player_id: int
    player_name: str
    eligible_positions: list[PositionKey]
    assigned_slot: SlotKey
    slot_index: int
    projected_fantasy_points: Decimal | None


class BenchAssignmentRead(DecimalStringMixin):
    draft_pick_id: int
    player_id: int
    player_name: str
    eligible_positions: list[PositionKey]
    bench_index: int
    projected_fantasy_points: Decimal | None


class UnassignedPlayerRead(DecimalStringMixin):
    draft_pick_id: int
    player_id: int
    player_name: str
    eligible_positions: list[PositionKey]
    reason: str
    projected_fantasy_points: Decimal | None


class AssistantReasonRead(BaseModel):
    code: ReasonCode
    position: PositionKey | None = None
    slots: list[SlotInstanceRead] = Field(default_factory=list)


class RosterSummaryRead(BaseModel):
    active_slots_total: int = Field(ge=0)
    active_slots_filled: int = Field(ge=0)
    active_slots_unfilled: int = Field(ge=0)
    bench_slots_total: int = Field(ge=0)
    bench_slots_filled: int = Field(ge=0)
    bench_slots_remaining: int = Field(ge=0)
    draftable_roster_capacity: int = Field(ge=0)
    players_drafted: int = Field(ge=0)
    roster_spots_remaining: int = Field(ge=0)
    assignments: list[RosterAssignmentRead]
    bench_assignments: list[BenchAssignmentRead]
    unfilled_slots: list[SlotInstanceRead]
    unassigned_players: list[UnassignedPlayerRead]


class AssistantPlayerRead(DecimalStringMixin):
    player_id: int
    player_name: str
    team: str | None
    primary_position: str | None
    eligible_positions: list[PositionKey]
    overall_rank: int | None
    overall_vor: Decimal | None
    best_value_position: PositionKey | None
    fantasy_points_per_game: Decimal
    projected_fantasy_points: Decimal
    position: PositionKey | None = None
    position_rank: int | None = None
    position_vor: Decimal | None = None
    matching_open_slots: list[SlotInstanceRead]
    reasons: list[AssistantReasonRead]


class BestByPositionRead(BaseModel):
    position: PositionKey
    items: list[AssistantPlayerRead]


class NextUserPickRead(BaseModel):
    next_overall_pick: int = Field(ge=1)
    next_round: int = Field(ge=1)
    next_pick_in_round: int = Field(ge=1)
    draft_position: int = Field(ge=1)
    picks_until: int = Field(ge=0)
    is_user_on_clock: bool
    is_consecutive_turn: bool
    turn_pick_number: int = Field(ge=1)
    consecutive_pick_numbers: list[int]
    consecutive_pick_overalls: list[int]


class AvailabilityOutlookRead(DecimalStringMixin):
    player_id: int
    player_name: str
    team: str | None
    eligible_positions: list[PositionKey]
    overall_rank: int | None
    available_rank: int = Field(ge=1)
    overall_vor: Decimal | None
    projected_fantasy_points: Decimal
    outlook: AvailabilityOutlook
    reasons: list[AssistantReasonRead]


class PositionScarcityRead(DecimalStringMixin):
    position: PositionKey
    top_player_id: int | None
    top_player_name: str | None
    top_position_vor: Decimal | None
    cutoff_player_id: int | None
    cutoff_player_name: str | None
    cutoff_position_vor: Decimal | None
    projected_vor_drop: Decimal | None
    players_before_next_pick: int = Field(ge=0)
    meaningful_options_remaining: int = Field(ge=0)
    severity: ScarcitySeverity
    reasons: list[AssistantReasonRead]


class ValueDropRead(DecimalStringMixin):
    scan_limit: int = Field(ge=1)
    meaningful_value_drop: Decimal
    drop_after_available_rank: int = Field(ge=1)
    before_player_id: int
    before_player_name: str
    before_overall_vor: Decimal | None
    after_player_id: int
    after_player_name: str
    after_overall_vor: Decimal | None
    gap: Decimal
    reasons: list[AssistantReasonRead]


class DraftIntelligenceRead(BaseModel):
    next_user_pick: NextUserPickRead | None
    availability_outlook: list[AvailabilityOutlookRead]
    positional_scarcity: list[PositionScarcityRead]
    value_drop: ValueDropRead | None


class DraftAssistantResponse(BaseModel):
    draft_id: int
    status: Literal["in_progress"]
    current_round: int
    current_overall_pick: int
    on_clock_team: AssistantTeamRead | None
    is_user_on_clock: bool
    user_team: UserTeamRead
    roster_summary: RosterSummaryRead
    best_available: list[AssistantPlayerRead]
    best_by_position: list[BestByPositionRead]
    roster_fit_options: list[AssistantPlayerRead]
    intelligence: DraftIntelligenceRead
