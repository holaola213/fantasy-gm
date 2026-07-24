from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.players.model import Player
from app.shared.database.session import AsyncSessionLocal


@dataclass(frozen=True)
class PlayerFixture:
    id: int
    full_name: str
    team: str
    primary_position: str
    is_active: bool = True


# Local development fixture IDs only. They are not NBA or ESPN identifiers.
PLAYER_FIXTURES = [
    PlayerFixture(1, "Nikola Jokic", "DEN", "C"),
    PlayerFixture(2, "Shai Gilgeous-Alexander", "OKC", "PG"),
    PlayerFixture(3, "Luka Doncic", "LAL", "PG"),
    PlayerFixture(4, "Giannis Antetokounmpo", "MIL", "PF"),
    PlayerFixture(5, "Anthony Edwards", "MIN", "SG"),
    PlayerFixture(6, "Jayson Tatum", "BOS", "SF"),
    PlayerFixture(7, "Victor Wembanyama", "SAS", "C"),
    PlayerFixture(8, "Stephen Curry", "GSW", "PG"),
    PlayerFixture(9, "Bam Adebayo", "MIA", "C"),
    PlayerFixture(10, "Paolo Banchero", "ORL", "PF"),
]


async def seed_players() -> int:
    rows = [fixture.__dict__ for fixture in PLAYER_FIXTURES]
    statement = insert(Player).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Player.id],
        set_={
            "full_name": statement.excluded.full_name,
            "team": statement.excluded.team,
            "primary_position": statement.excluded.primary_position,
            "is_active": statement.excluded.is_active,
            "updated_at": func.now(),
        },
    )

    async with AsyncSessionLocal() as session:
        await session.execute(statement)
        await session.commit()

    return len(rows)


async def main() -> None:
    seeded_count = await seed_players()
    print(f"Seeded {seeded_count} local development player fixtures.")


if __name__ == "__main__":
    asyncio.run(main())
