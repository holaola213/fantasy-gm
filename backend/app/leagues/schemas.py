from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

Platform = Literal["ESPN"]
ScoringFormat = Literal["points"]

VALID_ROSTER_SLOT_KEYS = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "BE", "IR"}


def normalize_key(value: str) -> str:
    return value.strip().upper()


class ScoringRuleBase(BaseModel):
    stat_key: str = Field(min_length=1, max_length=20)
    display_name: str = Field(min_length=1, max_length=80)
    points: Decimal
    sort_order: int = Field(ge=0)

    @field_validator("stat_key")
    @classmethod
    def normalize_stat_key(cls, value: str) -> str:
        return normalize_key(value)

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        return value.strip()

    @field_serializer("points", when_used="json")
    def serialize_points(self, value: Decimal) -> int | float:
        if value == value.to_integral_value():
            return int(value)
        return float(value)


class ScoringRuleRead(ScoringRuleBase):
    id: int
    league_id: int

    model_config = ConfigDict(from_attributes=True)


class RosterSlotBase(BaseModel):
    slot_key: str = Field(min_length=1, max_length=20)
    display_name: str = Field(min_length=1, max_length=80)
    count: int = Field(ge=0)
    sort_order: int = Field(ge=0)

    @field_validator("slot_key")
    @classmethod
    def normalize_slot_key(cls, value: str) -> str:
        normalized = normalize_key(value)
        if normalized not in VALID_ROSTER_SLOT_KEYS:
            raise ValueError("unsupported roster slot key")
        return normalized

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        return value.strip()


class RosterSlotRead(RosterSlotBase):
    id: int
    league_id: int

    model_config = ConfigDict(from_attributes=True)


class LeagueBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    platform: Platform
    season: int = Field(ge=2000, le=2100)
    team_count: int = Field(ge=2, le=30)
    scoring_format: ScoringFormat
    acquisition_limit_per_day: int | None = Field(default=None, ge=0, le=100)
    playoff_team_count: int = Field(ge=2)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class LeagueUpdate(LeagueBase):
    scoring_rules: list[ScoringRuleBase] = Field(min_length=1)
    roster_slots: list[RosterSlotBase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.playoff_team_count > self.team_count:
            raise ValueError("playoff_team_count cannot exceed team_count")

        stat_keys = [rule.stat_key for rule in self.scoring_rules]
        if len(stat_keys) != len(set(stat_keys)):
            raise ValueError("scoring rule stat_key values must be unique")

        slot_keys = [slot.slot_key for slot in self.roster_slots]
        if len(slot_keys) != len(set(slot_keys)):
            raise ValueError("roster slot_key values must be unique")

        if not any(slot.count > 0 for slot in self.roster_slots):
            raise ValueError("at least one roster slot count must be greater than zero")

        return self


class LeagueRead(LeagueBase):
    id: int
    created_at: datetime
    updated_at: datetime
    scoring_rules: list[ScoringRuleRead]
    roster_slots: list[RosterSlotRead]

    model_config = ConfigDict(from_attributes=True)
