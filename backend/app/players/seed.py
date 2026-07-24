from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from app.players.model import Player
from app.projections.providers import ProjectionProviderService
from app.shared.database.session import AsyncSessionLocal


@dataclass(frozen=True)
class PlayerFixture:
    id: int
    full_name: str
    team: str
    primary_position: str
    is_active: bool = True


# Local development fixture IDs only. They are not NBA or ESPN identifiers.
PROVIDER_PLAYERS = ProjectionProviderService().load_players()
PLAYER_FIXTURES = [
    PlayerFixture(
        int(player.source_player_id),
        player.full_name,
        player.team or "",
        player.primary_position or "",
        player.is_active,
    )
    for player in PROVIDER_PLAYERS
]


async def seed_players() -> int:
    async with AsyncSessionLocal() as session:
        fixture_names = [fixture.full_name for fixture in PLAYER_FIXTURES]
        existing_players = list(
            await session.scalars(select(Player).where(Player.full_name.in_(fixture_names)))
        )
        players_by_name = {player.full_name: player for player in existing_players}
        for fixture in PLAYER_FIXTURES:
            player = players_by_name.get(fixture.full_name)
            if player is None:
                player = Player(full_name=fixture.full_name)
                session.add(player)
            player.team = fixture.team
            player.primary_position = fixture.primary_position
            player.is_active = fixture.is_active
        await session.commit()

    return len(PLAYER_FIXTURES)


async def main() -> None:
    seeded_count = await seed_players()
    print(f"Seeded {seeded_count} local development player fixtures.")


if __name__ == "__main__":
    asyncio.run(main())
