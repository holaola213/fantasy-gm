from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.leagues.seed import seed_league
from app.main import app
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


def valid_payload() -> dict:
    return {
        "name": "12-Team ESPN Points League",
        "platform": "ESPN",
        "season": 2026,
        "team_count": 12,
        "scoring_format": "points",
        "acquisition_limit_per_day": 1,
        "playoff_team_count": 8,
        "scoring_rules": [
            {"stat_key": "fgm", "display_name": "Field Goals Made", "points": 1, "sort_order": 1},
            {"stat_key": "reb", "display_name": "Rebounds", "points": 1, "sort_order": 2},
            {"stat_key": "blk", "display_name": "Blocks", "points": 2, "sort_order": 3},
        ],
        "roster_slots": [
            {"slot_key": "pg", "display_name": "Point Guard", "count": 1, "sort_order": 1},
            {"slot_key": "util", "display_name": "Utility", "count": 3, "sort_order": 2},
        ],
    }


async def seed_test_league() -> None:
    from app.leagues import seed as seed_module

    async for session in app.dependency_overrides[get_session]():
        original_session_factory = seed_module.AsyncSessionLocal
        seed_module.AsyncSessionLocal = lambda: session
        try:
            await seed_league()
        finally:
            seed_module.AsyncSessionLocal = original_session_factory


@pytest.mark.asyncio
async def test_get_league_returns_safe_404_when_missing(client: AsyncClient) -> None:
    response = await client.get("/league")

    assert response.status_code == 404
    assert response.json() == {"detail": "league configuration not found"}


@pytest.mark.asyncio
async def test_get_league_returns_complete_nested_configuration(
    client: AsyncClient,
) -> None:
    await seed_test_league()

    response = await client.get("/league")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["platform"] == "ESPN"
    assert body["scoring_format"] == "points"
    assert len(body["scoring_rules"]) == 9
    assert len(body["roster_slots"]) == 10
    assert body["scoring_rules"][0]["stat_key"] == "FGM"
    assert body["roster_slots"][7]["slot_key"] == "UTIL"
    assert body["roster_slots"][7]["count"] == 3


@pytest.mark.asyncio
async def test_put_league_creates_singleton_and_normalizes_keys(
    client: AsyncClient,
) -> None:
    payload = valid_payload()

    response = await client.put("/league", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "12-Team ESPN Points League"
    assert [rule["stat_key"] for rule in body["scoring_rules"]] == [
        "FGM",
        "REB",
        "BLK",
    ]
    assert [slot["slot_key"] for slot in body["roster_slots"]] == ["PG", "UTIL"]


@pytest.mark.asyncio
async def test_put_league_updates_fields_and_replaces_children(
    client: AsyncClient,
) -> None:
    await client.put("/league", json=valid_payload())
    payload = valid_payload()
    payload["name"] = "Updated League"
    payload["team_count"] = 10
    payload["playoff_team_count"] = 6
    payload["scoring_rules"] = [
        {"stat_key": "ast", "display_name": "Assists", "points": 1.5, "sort_order": 1}
    ]
    payload["roster_slots"] = [
        {"slot_key": "be", "display_name": "Bench", "count": 5, "sort_order": 1}
    ]

    response = await client.put("/league", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated League"
    assert body["team_count"] == 10
    assert body["playoff_team_count"] == 6
    assert body["scoring_rules"] == [
        {
            "id": body["scoring_rules"][0]["id"],
            "league_id": 1,
            "stat_key": "AST",
            "display_name": "Assists",
            "points": 1.5,
            "sort_order": 1,
        }
    ]
    assert body["roster_slots"][0]["slot_key"] == "BE"


@pytest.mark.asyncio
async def test_invalid_team_and_playoff_counts_are_rejected(
    client: AsyncClient,
) -> None:
    payload = valid_payload()
    payload["team_count"] = 4
    payload["playoff_team_count"] = 8

    response = await client.put("/league", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_scoring_keys_are_rejected_after_normalization(
    client: AsyncClient,
) -> None:
    payload = valid_payload()
    payload["scoring_rules"] = [
        {"stat_key": "reb", "display_name": "Rebounds", "points": 1, "sort_order": 1},
        {"stat_key": " ReB ", "display_name": "Boards", "points": 1, "sort_order": 2},
    ]

    response = await client.put("/league", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_roster_slot_keys_are_rejected_after_normalization(
    client: AsyncClient,
) -> None:
    payload = valid_payload()
    payload["roster_slots"] = [
        {"slot_key": "util", "display_name": "Utility", "count": 3, "sort_order": 1},
        {"slot_key": " UTIL ", "display_name": "Utility 2", "count": 1, "sort_order": 2},
    ]

    response = await client.put("/league", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_scoring_rules_are_rejected(client: AsyncClient) -> None:
    payload = valid_payload()
    payload["scoring_rules"] = []

    response = await client.put("/league", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_all_zero_roster_configuration_is_rejected(
    client: AsyncClient,
) -> None:
    payload = valid_payload()
    payload["roster_slots"] = [
        {"slot_key": "PG", "display_name": "Point Guard", "count": 0, "sort_order": 1}
    ]

    response = await client.put("/league", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_platform_and_scoring_format_are_restricted(
    client: AsyncClient,
) -> None:
    payload = valid_payload()
    payload["platform"] = "Yahoo"
    payload["scoring_format"] = "categories"

    response = await client.put("/league", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transaction_rollback_preserves_prior_config_on_child_failure(
    client: AsyncClient,
) -> None:
    await client.put("/league", json=valid_payload())
    bad_payload = valid_payload()
    bad_payload["name"] = "Should Roll Back"
    bad_payload["scoring_rules"] = [
        {
            "stat_key": "PTS",
            "display_name": "Impossible Precision",
            "points": "123456789012345.1234",
            "sort_order": 1,
        }
    ]

    response = await client.put("/league", json=bad_payload)

    assert response.status_code == 500
    saved = (await client.get("/league")).json()
    assert saved["name"] == "12-Team ESPN Points League"
    assert [rule["stat_key"] for rule in saved["scoring_rules"]] == [
        "FGM",
        "REB",
        "BLK",
    ]


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_does_not_delete_unrelated_children() -> None:
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

        from app.leagues import seed as seed_module

        original_session_factory = seed_module.AsyncSessionLocal
        seed_engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema_name}},
        )
        seed_session_factory = async_sessionmaker(seed_engine, expire_on_commit=False)
        seed_module.AsyncSessionLocal = seed_session_factory

        try:
            assert await seed_league() == 1
            async with seed_session_factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO scoring_rules "
                        "(league_id, stat_key, display_name, points, sort_order) "
                        "VALUES (1, 'EXTRA', 'Extra Rule', :points, 99)"
                    ),
                    {"points": Decimal("0")},
                )
                await session.execute(
                    text(
                        "INSERT INTO roster_slots "
                        "(league_id, slot_key, display_name, count, sort_order) "
                        "VALUES (1, 'EXTRA', 'Extra Slot', 0, 99)"
                    )
                )
                await session.commit()

            assert await seed_league() == 1
        finally:
            seed_module.AsyncSessionLocal = original_session_factory
            await seed_engine.dispose()

        async with schema_engine.connect() as connection:
            scoring_count = await connection.scalar(
                text("SELECT count(*) FROM scoring_rules")
            )
            roster_count = await connection.scalar(
                text("SELECT count(*) FROM roster_slots")
            )
            extra_rule = await connection.scalar(
                text("SELECT display_name FROM scoring_rules WHERE stat_key = 'EXTRA'")
            )
            extra_slot = await connection.scalar(
                text("SELECT display_name FROM roster_slots WHERE slot_key = 'EXTRA'")
            )

        assert scoring_count == 10
        assert roster_count == 11
        assert extra_rule == "Extra Rule"
        assert extra_slot == "Extra Slot"
    finally:
        if "schema_engine" in locals():
            await schema_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await engine.dispose()
