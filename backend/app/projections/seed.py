from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.players.model import Player
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.providers import ProjectionProviderService
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
PROVIDER_PLAYERS = ProjectionProviderService().load_players()
PROJECTION_FIXTURES = [
    ProjectionFixture(
        int(player.source_player_id),
        player.games,
        player.minutes_per_game,
        player.fgm,
        player.fga,
        player.ftm,
        player.fta,
        player.rebounds,
        player.assists,
        player.steals,
        player.blocks,
        player.turnovers,
    )
    for player in PROVIDER_PLAYERS
]
PROVIDER_PLAYERS_BY_ID = {
    int(player.source_player_id): player
    for player in PROVIDER_PLAYERS
}


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

        fixture_names_by_id = {
            player_id: player.full_name
            for player_id, player in PROVIDER_PLAYERS_BY_ID.items()
        }
        existing_players = list(
            await session.scalars(
                select(Player).where(Player.full_name.in_(set(fixture_names_by_id.values())))
            )
        )
        players_by_name = {player.full_name: player for player in existing_players}
        missing_player_names = sorted(set(fixture_names_by_id.values()) - set(players_by_name))
        if missing_player_names:
            missing = ", ".join(missing_player_names)
            raise RuntimeError(
                "projection seed requires seeded player fixtures; "
                f"missing players: {missing}"
            )

        projection_rows = [
            {
                "projection_set_id": projection_set_id,
                **{
                    **fixture.__dict__,
                    "player_id": players_by_name[
                        fixture_names_by_id[fixture.player_id]
                    ].id,
                },
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
