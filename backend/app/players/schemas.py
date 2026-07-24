from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlayerRead(BaseModel):
    id: int
    full_name: str
    team: str | None
    primary_position: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlayerListResponse(BaseModel):
    items: list[PlayerRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
