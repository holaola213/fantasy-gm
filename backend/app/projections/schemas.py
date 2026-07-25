from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

ProjectionType = Literal["season"]
SortField = Literal[
    "player",
    "team",
    "position",
    "games",
    "minutes_per_game",
    "fantasy_points_per_game",
    "projected_fantasy_points",
]
SortDirection = Literal["asc", "desc"]


def normalize_source_key(value: str) -> str:
    return value.strip().lower()


class DecimalJsonMixin(BaseModel):
    @field_serializer(
        "games",
        "minutes_per_game",
        "fgm",
        "fga",
        "ftm",
        "fta",
        "rebounds",
        "assists",
        "steals",
        "blocks",
        "turnovers",
        "fantasy_points_per_game",
        "projected_fantasy_points",
        check_fields=False,
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> int | float:
        if value == value.to_integral_value():
            return int(value)
        return float(value)


class ProjectionSourceRead(BaseModel):
    id: int
    key: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectionSetRead(BaseModel):
    id: int
    source_id: int
    source: ProjectionSourceRead
    name: str
    season: int
    projection_type: ProjectionType
    as_of_date: date
    imported_at: datetime
    is_active: bool
    notes: str | None
    created_at: datetime
    player_count: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class ProjectionPlayerRead(DecimalJsonMixin):
    player_id: int
    full_name: str
    team: str | None
    primary_position: str | None
    games: Decimal = Field(ge=0, le=82)
    minutes_per_game: Decimal = Field(ge=0, le=60)
    fgm: Decimal = Field(ge=0)
    fga: Decimal = Field(ge=0)
    ftm: Decimal = Field(ge=0)
    fta: Decimal = Field(ge=0)
    rebounds: Decimal = Field(ge=0)
    assists: Decimal = Field(ge=0)
    steals: Decimal = Field(ge=0)
    blocks: Decimal = Field(ge=0)
    turnovers: Decimal = Field(ge=0)
    fantasy_points_per_game: Decimal
    projected_fantasy_points: Decimal


class ProjectionPlayerListResponse(BaseModel):
    items: list[ProjectionPlayerRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class ProjectionSetListResponse(BaseModel):
    items: list[ProjectionSetRead]


class ProjectionSourceListResponse(BaseModel):
    items: list[ProjectionSourceRead]


class ProjectionSourceSeed(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return normalize_source_key(value)
