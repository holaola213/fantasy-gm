from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.drafts.schemas import EligibilitySeedRow
from app.players.model import Player, PlayerEligibility
from app.players.seed import PLAYER_FIXTURES
from app.shared.database.session import AsyncSessionLocal


@dataclass(frozen=True)
class EligibilityFixture:
    full_name: str
    positions: tuple[str, ...]


# Local development eligibility fixture values only. They are not ESPN or NBA
# identifiers and should be replaced by real source imports in a later milestone.
ELIGIBILITY_FIXTURES = [
    EligibilityFixture("Nikola Jokic", ("C",)),
    EligibilityFixture("Shai Gilgeous-Alexander", ("PG", "SG")),
    EligibilityFixture("Luka Doncic", ("PG", "SG")),
    EligibilityFixture("Giannis Antetokounmpo", ("PF", "C")),
    EligibilityFixture("Anthony Edwards", ("SG", "SF")),
    EligibilityFixture("Jayson Tatum", ("SF", "PF")),
    EligibilityFixture("Victor Wembanyama", ("PF", "C")),
    EligibilityFixture("Stephen Curry", ("PG",)),
    EligibilityFixture("Bam Adebayo", ("PF", "C")),
    EligibilityFixture("Paolo Banchero", ("SF", "PF")),
]


async def seed_draft_eligibilities() -> int:
    expected_names = {fixture.full_name for fixture in PLAYER_FIXTURES}
    fixture_names = {fixture.full_name for fixture in ELIGIBILITY_FIXTURES}
    missing_fixture_names = sorted(expected_names - fixture_names)
    if missing_fixture_names:
        missing = ", ".join(missing_fixture_names)
        raise RuntimeError(f"eligibility seed has no fixture for players: {missing}")

    async with AsyncSessionLocal() as session:
        players = list(
            await session.scalars(
                select(Player).where(Player.full_name.in_(expected_names))
            )
        )
        players_by_name = {player.full_name: player for player in players}
        missing_players = sorted(expected_names - set(players_by_name))
        if missing_players:
            missing = ", ".join(missing_players)
            raise RuntimeError(
                "draft eligibility seed requires seeded player fixtures; "
                f"missing players: {missing}"
            )

        rows = []
        for fixture in ELIGIBILITY_FIXTURES:
            player = players_by_name[fixture.full_name]
            for position_key in fixture.positions:
                validated = EligibilitySeedRow(
                    player_id=player.id,
                    position_key=position_key,
                )
                rows.append(validated.model_dump())

        statement = insert(PlayerEligibility).values(rows)
        statement = statement.on_conflict_do_nothing(
            constraint="uq_player_eligibilities_player_position"
        )
        await session.execute(statement)
        await session.commit()

    return len(rows)


async def main() -> None:
    seeded_count = await seed_draft_eligibilities()
    print(f"Seeded {seeded_count} local development player eligibility fixtures.")


if __name__ == "__main__":
    asyncio.run(main())
