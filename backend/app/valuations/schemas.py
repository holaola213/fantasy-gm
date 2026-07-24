from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.drafts.schemas import PositionKey, SortDirection

ValuationSortField = Literal[
    "player",
    "team",
    "position",
    "fantasy_points_per_game",
    "projected_fantasy_points",
    "overall_vor",
    "overall_rank",
]


class DecimalStringMixin(BaseModel):
    @field_serializer(
        "projected_games",
        "fantasy_points_per_game",
        "projected_fantasy_points",
        "replacement_fantasy_points",
        "vor",
        "overall_vor",
        check_fields=False,
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value.quantize(Decimal("0.01")))


class PositionValueRead(DecimalStringMixin):
    position: PositionKey
    replacement_player_id: int
    replacement_player_name: str
    replacement_fantasy_points: Decimal
    vor: Decimal
    position_rank: int


class PlayerValuationRead(DecimalStringMixin):
    player_id: int
    player_name: str
    team: str | None
    primary_position: str | None
    eligible_positions: list[PositionKey]
    compatible_roster_slots: list[str]
    projected_games: Decimal
    fantasy_points_per_game: Decimal
    projected_fantasy_points: Decimal
    position_values: list[PositionValueRead]
    overall_vor: Decimal | None
    best_value_position: PositionKey | None
    overall_rank: int | None


class ValuationListResponse(BaseModel):
    items: list[PlayerValuationRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    projection_set_id: int
    projection_set_name: str
    projection_set_as_of_date: date


class ActiveSlotDemandRead(BaseModel):
    slot_key: str
    count: int


class ReplacementLevelRead(DecimalStringMixin):
    position: PositionKey
    demand: int
    replacement_player_id: int
    replacement_player_name: str
    replacement_fantasy_points: Decimal


class ReplacementLevelsResponse(BaseModel):
    projection_set_id: int
    projection_set_name: str
    projection_set_as_of_date: date
    team_count: int
    active_slot_demand: list[ActiveSlotDemandRead]
    total_active_demand: int
    drafted_player_target: int
    positions: list[ReplacementLevelRead]


__all__ = [
    "PlayerValuationRead",
    "PositionValueRead",
    "ReplacementLevelsResponse",
    "SortDirection",
    "ValuationListResponse",
    "ValuationSortField",
]
