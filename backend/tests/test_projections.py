from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.players.model import Player
from app.players.seed import PLAYER_FIXTURES, seed_players
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.seed import seed_projections
from app.shared.config.settings import get_settings
from app.shared.database.base import Base
from app.shared.database.session import get_session
from app.shared.fixtures.development import DEVELOPMENT_PLAYER_FIXTURES


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    settings = get_settings()
    database_url = settings.database_url
    schema_name = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(database_url)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    await admin_engine.dispose()

    engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await engine.dispose()


def league_payload() -> dict:
    return {
        "name": "Projection Test League",
        "platform": "ESPN",
        "season": 2026,
        "team_count": 12,
        "scoring_format": "points",
        "acquisition_limit_per_day": 1,
        "playoff_team_count": 8,
        "scoring_rules": [
            {"stat_key": "FGM", "display_name": "Field Goals Made", "points": 1, "sort_order": 1},
            {"stat_key": "FGA", "display_name": "Field Goals Attempted", "points": -1, "sort_order": 2},
            {"stat_key": "REB", "display_name": "Rebounds", "points": 1, "sort_order": 3},
        ],
        "roster_slots": [
            {"slot_key": "PG", "display_name": "Point Guard", "count": 1, "sort_order": 1},
        ],
    }


async def seed_test_players() -> None:
    async for session in app.dependency_overrides[get_session]():
        rows = [fixture.__dict__ for fixture in PLAYER_FIXTURES]
        statement = insert(Player).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[Player.id],
            set_={
                "full_name": statement.excluded.full_name,
                "team": statement.excluded.team,
                "primary_position": statement.excluded.primary_position,
                "is_active": statement.excluded.is_active,
            },
        )
        await session.execute(statement)
        await session.commit()


async def seed_test_projection_set() -> int:
    async for session in app.dependency_overrides[get_session]():
        source = ProjectionSource(
            key="manual",
            name="Manual Development Projections",
            description="Test source",
            is_active=True,
        )
        session.add(source)
        await session.flush()
        projection_set = ProjectionSet(
            source_id=source.id,
            name="Manual 2026 Season Projection Set",
            season=2026,
            projection_type="season",
            as_of_date=date(2026, 7, 24),
            is_active=True,
            notes="Test set",
        )
        session.add(projection_set)
        await session.flush()
        session.add_all(
            [
                PlayerProjection(
                    projection_set_id=projection_set.id,
                    player_id=1,
                    games=Decimal("70.50"),
                    minutes_per_game=Decimal("34.25"),
                    fgm=Decimal("10.000"),
                    fga=Decimal("18.000"),
                    ftm=Decimal("5.000"),
                    fta=Decimal("6.000"),
                    rebounds=Decimal("12.000"),
                    assists=Decimal("8.000"),
                    steals=Decimal("1.000"),
                    blocks=Decimal("1.000"),
                    turnovers=Decimal("3.000"),
                ),
                PlayerProjection(
                    projection_set_id=projection_set.id,
                    player_id=2,
                    games=Decimal("72.00"),
                    minutes_per_game=Decimal("35.00"),
                    fgm=Decimal("9.000"),
                    fga=Decimal("19.000"),
                    ftm=Decimal("7.000"),
                    fta=Decimal("8.000"),
                    rebounds=Decimal("5.000"),
                    assists=Decimal("6.000"),
                    steals=Decimal("2.000"),
                    blocks=Decimal("1.000"),
                    turnovers=Decimal("2.000"),
                ),
                PlayerProjection(
                    projection_set_id=projection_set.id,
                    player_id=5,
                    games=Decimal("68.50"),
                    minutes_per_game=Decimal("33.00"),
                    fgm=Decimal("8.000"),
                    fga=Decimal("17.000"),
                    ftm=Decimal("4.000"),
                    fta=Decimal("5.000"),
                    rebounds=Decimal("6.000"),
                    assists=Decimal("5.000"),
                    steals=Decimal("1.000"),
                    blocks=Decimal("0.000"),
                    turnovers=Decimal("2.000"),
                ),
            ]
        )
        await session.commit()
        return projection_set.id
    raise RuntimeError("test projection seed failed")


@pytest.mark.asyncio
async def test_projection_sources_and_sets_are_listed(client: AsyncClient) -> None:
    await seed_test_players()
    projection_set_id = await seed_test_projection_set()

    sources_response = await client.get("/projection-sources")
    sets_response = await client.get("/projection-sets")
    detail_response = await client.get(f"/projection-sets/{projection_set_id}")

    assert sources_response.status_code == 200
    assert sources_response.json()["items"][0]["key"] == "manual"
    assert sets_response.status_code == 200
    assert sets_response.json()["items"][0]["projection_type"] == "season"
    assert detail_response.status_code == 200
    assert detail_response.json()["source"]["key"] == "manual"


@pytest.mark.asyncio
async def test_projection_set_detail_returns_safe_404(client: AsyncClient) -> None:
    response = await client.get("/projection-sets/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "projection set not found"}


@pytest.mark.asyncio
async def test_projection_players_require_league_configuration(
    client: AsyncClient,
) -> None:
    await seed_test_players()
    projection_set_id = await seed_test_projection_set()

    response = await client.get(f"/projection-sets/{projection_set_id}/players")

    assert response.status_code == 409
    assert response.json() == {"detail": "league configuration required"}


@pytest.mark.asyncio
async def test_projection_players_include_decimal_fantasy_calculations(
    client: AsyncClient,
) -> None:
    await seed_test_players()
    projection_set_id = await seed_test_projection_set()
    await client.put("/league", json=league_payload())

    response = await client.get(
        f"/projection-sets/{projection_set_id}/players",
        params={"sort": "player", "direction": "asc"},
    )

    assert response.status_code == 200
    body = response.json()
    jokic = next(item for item in body["items"] if item["full_name"] == "Nikola Jokic")
    assert body["total"] == 3
    assert jokic["full_name"] == "Nikola Jokic"
    assert jokic["games"] == 70.5
    assert jokic["fantasy_points_per_game"] == 4
    assert jokic["projected_fantasy_points"] == 282


@pytest.mark.asyncio
async def test_projection_players_support_search_filters_and_pagination(
    client: AsyncClient,
) -> None:
    await seed_test_players()
    projection_set_id = await seed_test_projection_set()
    await client.put("/league", json=league_payload())

    response = await client.get(
        f"/projection-sets/{projection_set_id}/players",
        params={"team": "okc", "position": "pg", "limit": 1, "offset": 0},
    )
    search_response = await client.get(
        f"/projection-sets/{projection_set_id}/players",
        params={"search": "edwards"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["full_name"] == "Shai Gilgeous-Alexander"
    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["full_name"] == "Anthony Edwards"


@pytest.mark.asyncio
async def test_projection_players_support_sorting_and_validation(
    client: AsyncClient,
) -> None:
    await seed_test_players()
    projection_set_id = await seed_test_projection_set()
    await client.put("/league", json=league_payload())

    minutes_response = await client.get(
        f"/projection-sets/{projection_set_id}/players",
        params={"sort": "minutes_per_game", "direction": "desc"},
    )
    fantasy_response = await client.get(
        f"/projection-sets/{projection_set_id}/players",
        params={"sort": "projected_fantasy_points", "direction": "asc"},
    )
    invalid_response = await client.get(
        f"/projection-sets/{projection_set_id}/players",
        params={"sort": "minutes"},
    )

    assert minutes_response.status_code == 200
    assert minutes_response.json()["items"][0]["full_name"] == "Shai Gilgeous-Alexander"
    assert fantasy_response.status_code == 200
    assert fantasy_response.json()["items"][0]["full_name"] == "Shai Gilgeous-Alexander"
    assert invalid_response.status_code == 422


@pytest.mark.asyncio
async def test_projection_constraints_are_enforced(client: AsyncClient) -> None:
    await seed_test_players()
    projection_set_id = await seed_test_projection_set()

    async for session in app.dependency_overrides[get_session]():
        session.add(
            PlayerProjection(
                projection_set_id=projection_set_id,
                player_id=3,
                games=Decimal("83.00"),
                minutes_per_game=Decimal("30.00"),
                fgm=Decimal("1.000"),
                fga=Decimal("2.000"),
                ftm=Decimal("1.000"),
                fta=Decimal("2.000"),
                rebounds=Decimal("1.000"),
                assists=Decimal("1.000"),
                steals=Decimal("1.000"),
                blocks=Decimal("1.000"),
                turnovers=Decimal("1.000"),
            )
        )
        with pytest.raises(Exception):
            await session.commit()


@pytest.mark.asyncio
async def test_only_one_active_projection_set_per_source_season_type(
    client: AsyncClient,
) -> None:
    async for session in app.dependency_overrides[get_session]():
        source = ProjectionSource(
            key="manual",
            name="Manual Development Projections",
            is_active=True,
        )
        session.add(source)
        await session.flush()
        session.add_all(
            [
                ProjectionSet(
                    source_id=source.id,
                    name="First Active Set",
                    season=2026,
                    projection_type="season",
                    as_of_date=date(2026, 7, 1),
                    is_active=True,
                ),
                ProjectionSet(
                    source_id=source.id,
                    name="Second Active Set",
                    season=2026,
                    projection_type="season",
                    as_of_date=date(2026, 7, 24),
                    is_active=True,
                ),
            ]
        )
        with pytest.raises(Exception):
            await session.commit()


@pytest.mark.asyncio
async def test_projection_seed_reports_missing_player_fixtures() -> None:
    settings = get_settings()
    database_url = settings.database_url
    schema_name = f"test_{uuid4().hex}"
    engine = create_async_engine(database_url)

    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        schema_engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema_name}},
        )
        async with schema_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        from app.projections import seed as projections_seed_module

        original_projection_session_factory = projections_seed_module.AsyncSessionLocal
        seed_engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema_name}},
        )
        seed_session_factory = async_sessionmaker(seed_engine, expire_on_commit=False)
        projections_seed_module.AsyncSessionLocal = seed_session_factory

        try:
            with pytest.raises(RuntimeError, match="missing players"):
                await seed_projections()
        finally:
            projections_seed_module.AsyncSessionLocal = (
                original_projection_session_factory
            )
            await seed_engine.dispose()
    finally:
        if "schema_engine" in locals():
            await schema_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_keeps_unrelated_projection_rows() -> None:
    settings = get_settings()
    database_url = settings.database_url
    schema_name = f"test_{uuid4().hex}"
    engine = create_async_engine(database_url)

    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        schema_engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema_name}},
        )
        async with schema_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        from app.players import seed as players_seed_module
        from app.projections import seed as projections_seed_module

        original_player_session_factory = players_seed_module.AsyncSessionLocal
        original_projection_session_factory = projections_seed_module.AsyncSessionLocal
        seed_engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema_name}},
        )
        seed_session_factory = async_sessionmaker(seed_engine, expire_on_commit=False)
        players_seed_module.AsyncSessionLocal = seed_session_factory
        projections_seed_module.AsyncSessionLocal = seed_session_factory

        try:
            assert await seed_players() == len(DEVELOPMENT_PLAYER_FIXTURES)
            assert await seed_projections() == len(DEVELOPMENT_PLAYER_FIXTURES)
            async with seed_session_factory() as session:
                source_id = await session.scalar(
                    text("SELECT id FROM projection_sources WHERE key = 'manual'")
                )
                session.add(
                    ProjectionSet(
                        source_id=source_id,
                        name="Historical Manual Set",
                        season=2026,
                        projection_type="season",
                        as_of_date=date(2026, 7, 1),
                        is_active=False,
                    )
                )
                await session.commit()

            assert await seed_projections() == len(DEVELOPMENT_PLAYER_FIXTURES)
        finally:
            players_seed_module.AsyncSessionLocal = original_player_session_factory
            projections_seed_module.AsyncSessionLocal = original_projection_session_factory
            await seed_engine.dispose()

        async with schema_engine.connect() as connection:
            source_count = await connection.scalar(text("SELECT count(*) FROM projection_sources"))
            set_count = await connection.scalar(text("SELECT count(*) FROM projection_sets"))
            row_count = await connection.scalar(text("SELECT count(*) FROM player_projections"))

        assert source_count == 1
        assert set_count == 2
        assert row_count == len(DEVELOPMENT_PLAYER_FIXTURES)
    finally:
        if "schema_engine" in locals():
            await schema_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await engine.dispose()
