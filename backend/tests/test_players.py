from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.players.seed import seed_players
from app.shared.fixtures.development import DEVELOPMENT_PLAYER_FIXTURES
from app.shared.config.settings import get_settings
from app.shared.database.base import Base
from app.shared.database.session import get_session


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


async def seed_test_players() -> None:
    async for session in app.dependency_overrides[get_session]():
        from app.players.seed import PLAYER_FIXTURES
        from sqlalchemy.dialects.postgresql import insert
        from app.players.model import Player

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


@pytest.mark.asyncio
async def test_list_players_returns_envelope(client: AsyncClient) -> None:
    await seed_test_players()

    response = await client.get("/players")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(DEVELOPMENT_PLAYER_FIXTURES)
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 50
    assert {"id", "full_name", "team", "primary_position", "is_active"} <= set(
        body["items"][0]
    )


@pytest.mark.asyncio
async def test_get_player_returns_detail(client: AsyncClient) -> None:
    await seed_test_players()

    response = await client.get("/players/1")

    assert response.status_code == 200
    assert response.json()["full_name"] == "Nikola Jokic"


@pytest.mark.asyncio
async def test_get_player_returns_safe_404(client: AsyncClient) -> None:
    response = await client.get("/players/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "player not found"}


@pytest.mark.asyncio
async def test_search_is_case_insensitive_and_full_name_only(
    client: AsyncClient,
) -> None:
    await seed_test_players()

    response = await client.get("/players", params={"search": "jOkIc"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["full_name"] == "Nikola Jokic"


@pytest.mark.asyncio
async def test_team_position_and_active_filters_are_case_insensitive(
    client: AsyncClient,
) -> None:
    await seed_test_players()

    response = await client.get(
        "/players", params={"team": "den", "position": "c", "active": "true"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["full_name"] == "Nikola Jokic"


@pytest.mark.asyncio
async def test_pagination_total_counts_matches_before_pagination(
    client: AsyncClient,
) -> None:
    await seed_test_players()

    response = await client.get("/players", params={"limit": 3, "offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(DEVELOPMENT_PLAYER_FIXTURES)
    assert body["limit"] == 3
    assert body["offset"] == 2
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_invalid_pagination_returns_validation_error(
    client: AsyncClient,
) -> None:
    response = await client.get("/players", params={"limit": 0, "offset": -1})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_does_not_delete_unrelated_players() -> None:
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
            await connection.execute(
                text(
                    "INSERT INTO players "
                    "(id, full_name, team, primary_position, is_active) "
                    "VALUES (999, 'Unrelated Player', NULL, NULL, true)"
                )
            )

        from app.players import seed as seed_module

        original_session_factory = seed_module.AsyncSessionLocal
        seed_engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema_name}},
        )
        seed_session_factory = async_sessionmaker(seed_engine, expire_on_commit=False)
        seed_module.AsyncSessionLocal = seed_session_factory

        try:
            assert await seed_players() == len(DEVELOPMENT_PLAYER_FIXTURES)
            assert await seed_players() == len(DEVELOPMENT_PLAYER_FIXTURES)
        finally:
            seed_module.AsyncSessionLocal = original_session_factory
            await seed_engine.dispose()

        async with engine.connect() as connection:
            await connection.execute(text(f'SET search_path TO "{schema_name}"'))
            count = await connection.scalar(text("SELECT count(*) FROM players"))
            unrelated = await connection.scalar(
                text("SELECT full_name FROM players WHERE id = 999")
            )

        assert count == len(DEVELOPMENT_PLAYER_FIXTURES) + 1
        assert unrelated == "Unrelated Player"
    finally:
        if "schema_engine" in locals():
            await schema_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await engine.dispose()
