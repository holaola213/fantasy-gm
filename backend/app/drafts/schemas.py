from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.drafts.compatibility import normalize_position_key

DraftStatus = Literal["setup", "in_progress", "completed"]
DraftType = Literal["snake"]
DraftSortField = Literal[
    "player",
    "team",
    "position",
    "fantasy_points_per_game",
    "projected_fantasy_points",
]
SortDirection = Literal["asc", "desc"]
PositionKey = Literal["PG", "SG", "SF", "PF", "C"]


class DecimalJsonMixin(BaseModel):
    @field_serializer(
        "fantasy_points_per_game",
        "projected_fantasy_points",
        check_fields=False,
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> int | float:
        if value == value.to_integral_value():
            return int(value)
        return float(value)


class EligibilityRead(BaseModel):
    player_id: int
    eligible_positions: list[PositionKey]
    compatible_roster_slots: list[str]


class FantasyTeamSetup(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    draft_position: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("team name cannot be blank")
        return trimmed


class DraftCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    teams: list[FantasyTeamSetup] = Field(min_length=2)
    user_draft_position: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("draft name cannot be blank")
        return trimmed

    @model_validator(mode="after")
    def validate_team_positions(self):
        positions = [team.draft_position for team in self.teams]
        expected = set(range(1, len(self.teams) + 1))
        if set(positions) != expected:
            raise ValueError("draft positions must be complete and sequential")
        if self.user_draft_position not in expected:
            raise ValueError("user draft position must match a team")
        return self


class DraftSetupUpdate(DraftCreate):
    pass


class FantasyTeamRead(BaseModel):
    id: int
    draft_session_id: int
    name: str
    draft_position: int
    is_user_team: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftPickRead(BaseModel):
    id: int
    draft_session_id: int
    fantasy_team_id: int
    player_id: int
    player_name: str
    team: str | None
    primary_position: str | None
    eligible_positions: list[PositionKey]
    compatible_roster_slots: list[str]
    fantasy_team_name: str
    round_number: int
    pick_in_round: int
    overall_pick: int
    created_at: datetime


class DraftSessionRead(BaseModel):
    id: int
    league_id: int
    projection_set_id: int
    name: str
    season: int
    draft_type: DraftType
    status: DraftStatus
    team_count: int
    rounds: int
    current_pick_number: int | None
    current_round: int | None
    current_pick_in_round: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftBoardResponse(BaseModel):
    draft: DraftSessionRead
    on_clock_team: FantasyTeamRead | None
    teams: list[FantasyTeamRead]
    picks: list[DraftPickRead]
    recent_picks: list[DraftPickRead]


class DraftTeamDetailResponse(BaseModel):
    team: FantasyTeamRead
    picks: list[DraftPickRead]


class DraftPickCreate(BaseModel):
    player_id: int = Field(ge=1)


class AvailablePlayerRead(DecimalJsonMixin):
    player_id: int
    full_name: str
    team: str | None
    primary_position: str | None
    eligible_positions: list[PositionKey]
    compatible_roster_slots: list[str]
    fantasy_points_per_game: Decimal
    projected_fantasy_points: Decimal


class AvailablePlayerListResponse(BaseModel):
    items: list[AvailablePlayerRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class EligibilitySeedRow(BaseModel):
    player_id: int
    position_key: PositionKey

    @field_validator("position_key", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return normalize_position_key(value)
