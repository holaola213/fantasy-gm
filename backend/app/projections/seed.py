from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.players.model import Player
from app.players.seed import PLAYER_FIXTURES
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.schemas import normalize_source_key
from app.shared.database.session import AsyncSessionLocal


@dataclass(frozen=True)
class ProjectionFixture:
    player_id: int
    games: Decimal
    minutes_per_game: Decimal
    fgm: Decimal
    fga: Decimal
    ftm: Decimal
    fta: Decimal
    rebounds: Decimal
    assists: Decimal
    steals: Decimal
    blocks: Decimal
    turnovers: Decimal


SOURCE_KEY = "manual"
PROJECTION_SEASON = 2026
PROJECTION_TYPE = "season"
AS_OF_DATE = date(2026, 7, 24)

# Local development fixture values only. Future real imports should create new
# immutable projection sets instead of updating historical projection sets.
PROJECTION_FIXTURES = [
    ProjectionFixture(1, Decimal("70.5"), Decimal("34.2"), Decimal("10.8"), Decimal("18.9"), Decimal("5.1"), Decimal("6.3"), Decimal("12.4"), Decimal("9.2"), Decimal("1.4"), Decimal("0.9"), Decimal("3.1")),
    ProjectionFixture(2, Decimal("72.0"), Decimal("34.8"), Decimal("10.5"), Decimal("21.0"), Decimal("8.2"), Decimal("9.1"), Decimal("5.6"), Decimal("6.4"), Decimal("1.8"), Decimal("1.0"), Decimal("2.4")),
    ProjectionFixture(3, Decimal("68.5"), Decimal("35.4"), Decimal("9.8"), Decimal("20.7"), Decimal("6.7"), Decimal("8.2"), Decimal("8.5"), Decimal("9.1"), Decimal("1.4"), Decimal("0.5"), Decimal("3.7")),
    ProjectionFixture(4, Decimal("66.0"), Decimal("32.6"), Decimal("11.2"), Decimal("19.0"), Decimal("7.0"), Decimal("10.8"), Decimal("11.1"), Decimal("6.2"), Decimal("1.2"), Decimal("1.1"), Decimal("3.0")),
    ProjectionFixture(5, Decimal("74.0"), Decimal("35.0"), Decimal("9.4"), Decimal("20.8"), Decimal("5.0"), Decimal("6.2"), Decimal("5.7"), Decimal("5.0"), Decimal("1.3"), Decimal("0.6"), Decimal("2.8")),
    ProjectionFixture(6, Decimal("70.0"), Decimal("36.1"), Decimal("9.1"), Decimal("19.8"), Decimal("5.8"), Decimal("6.9"), Decimal("8.0"), Decimal("5.3"), Decimal("1.1"), Decimal("0.7"), Decimal("2.5")),
    ProjectionFixture(7, Decimal("69.5"), Decimal("31.8"), Decimal("8.9"), Decimal("18.5"), Decimal("4.7"), Decimal("5.8"), Decimal("10.7"), Decimal("4.1"), Decimal("1.2"), Decimal("3.4"), Decimal("3.3")),
    ProjectionFixture(8, Decimal("65.0"), Decimal("32.4"), Decimal("8.5"), Decimal("18.4"), Decimal("4.3"), Decimal("4.8"), Decimal("4.5"), Decimal("6.1"), Decimal("1.1"), Decimal("0.4"), Decimal("2.9")),
    ProjectionFixture(9, Decimal("71.0"), Decimal("33.1"), Decimal("7.4"), Decimal("13.9"), Decimal("3.9"), Decimal("5.2"), Decimal("10.2"), Decimal("4.0"), Decimal("1.1"), Decimal("0.9"), Decimal("2.1")),
    ProjectionFixture(10, Decimal("73.0"), Decimal("34.0"), Decimal("8.8"), Decimal("18.7"), Decimal("5.6"), Decimal("7.2"), Decimal("7.4"), Decimal("5.4"), Decimal("1.0"), Decimal("0.7"), Decimal("2.7")),
]


async def seed_projections() -> int:
    async with AsyncSessionLocal() as session:
        source_statement = insert(ProjectionSource).values(
            key=normalize_source_key(SOURCE_KEY),
            name="Manual Development Projections",
            description="Local deterministic manual projection source.",
            is_active=True,
        )
        source_statement = source_statement.on_conflict_do_update(
            constraint="uq_projection_sources_key",
            set_={
                "name": source_statement.excluded.name,
                "description": source_statement.excluded.description,
                "is_active": source_statement.excluded.is_active,
                "updated_at": func.now(),
            },
        )
        await session.execute(source_statement)
        source_id = await session.scalar(
            select(ProjectionSource.id).where(ProjectionSource.key == SOURCE_KEY)
        )
        if source_id is None:
            raise RuntimeError("projection source seed failed")

        set_statement = insert(ProjectionSet).values(
            source_id=source_id,
            name="Manual 2026 Season Projection Set",
            season=PROJECTION_SEASON,
            projection_type=PROJECTION_TYPE,
            as_of_date=AS_OF_DATE,
            is_active=True,
            notes=(
                "Local development fixture set. Future real imports create new "
                "immutable projection sets."
            ),
        )
        set_statement = set_statement.on_conflict_do_update(
            constraint="uq_projection_sets_source_season_type_as_of",
            set_={
                "name": set_statement.excluded.name,
                "is_active": set_statement.excluded.is_active,
                "notes": set_statement.excluded.notes,
                "imported_at": func.now(),
            },
        )
        await session.execute(set_statement)
        projection_set_id = await session.scalar(
            select(ProjectionSet.id).where(
                ProjectionSet.source_id == source_id,
                ProjectionSet.season == PROJECTION_SEASON,
                ProjectionSet.projection_type == PROJECTION_TYPE,
                ProjectionSet.as_of_date == AS_OF_DATE,
            )
        )
        if projection_set_id is None:
            raise RuntimeError("projection set seed failed")

        fixture_player_ids = {fixture.id for fixture in PLAYER_FIXTURES}
        existing_player_ids = set(
            await session.scalars(
                select(Player.id).where(Player.id.in_(fixture_player_ids))
            )
        )
        missing_player_ids = sorted(fixture_player_ids - existing_player_ids)
        if missing_player_ids:
            missing = ", ".join(str(player_id) for player_id in missing_player_ids)
            raise RuntimeError(
                "projection seed requires seeded player fixtures; "
                f"missing player ids: {missing}"
            )

        projection_rows = [
            {
                "projection_set_id": projection_set_id,
                **fixture.__dict__,
            }
            for fixture in PROJECTION_FIXTURES
        ]
        projection_statement = insert(PlayerProjection).values(projection_rows)
        projection_statement = projection_statement.on_conflict_do_update(
            constraint="uq_player_projections_set_player",
            set_={
                "games": projection_statement.excluded.games,
                "minutes_per_game": projection_statement.excluded.minutes_per_game,
                "fgm": projection_statement.excluded.fgm,
                "fga": projection_statement.excluded.fga,
                "ftm": projection_statement.excluded.ftm,
                "fta": projection_statement.excluded.fta,
                "rebounds": projection_statement.excluded.rebounds,
                "assists": projection_statement.excluded.assists,
                "steals": projection_statement.excluded.steals,
                "blocks": projection_statement.excluded.blocks,
                "turnovers": projection_statement.excluded.turnovers,
            },
        )
        await session.execute(projection_statement)
        await session.commit()

    return len(projection_rows)


async def main() -> None:
    seeded_count = await seed_projections()
    print(f"Seeded {seeded_count} local development projection fixtures.")


if __name__ == "__main__":
    asyncio.run(main())
