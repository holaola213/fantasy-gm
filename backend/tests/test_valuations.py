from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.leagues.model import ScoringRule
from app.drafts.model import DraftPick
from app.drafts.seed import seed_draft_eligibilities
from app.leagues.seed import seed_league
from app.main import app
from app.players.model import Player, PlayerEligibility
from app.players.seed import seed_players
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource
from app.projections.seed import seed_projections
from app.shared.config.settings import get_settings
from app.shared.database.base import Base
from app.shared.database.session import get_session
from app.shared.fixtures.development import DEVELOPMENT_PLAYER_FIXTURES
from app.valuations.replacement import (
    ValuationCandidate,
    calculate_replacement_levels,
)
from app.valuations import service as valuation_service_module
from app.valuations.service import ValuationService


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    settings = get_settings()
    schema_name = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    await admin_engine.dispose()

    engine = create_async_engine(
        settings.database_url,
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
            test_client.session_factory = session_factory
            yield test_client
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await engine.dispose()


def league_payload(team_count: int = 2) -> dict:
    return {
        "name": "Valuation Test League",
        "platform": "ESPN",
        "season": 2026,
        "team_count": team_count,
        "scoring_format": "points",
        "acquisition_limit_per_day": None,
        "playoff_team_count": 2,
        "scoring_rules": [
            {"stat_key": "FGM", "display_name": "Field Goals Made", "points": 1, "sort_order": 1},
        ],
        "roster_slots": [
            {"slot_key": "PG", "display_name": "Point Guard", "count": 1, "sort_order": 1},
            {"slot_key": "SG", "display_name": "Shooting Guard", "count": 1, "sort_order": 2},
            {"slot_key": "SF", "display_name": "Small Forward", "count": 1, "sort_order": 3},
            {"slot_key": "PF", "display_name": "Power Forward", "count": 1, "sort_order": 4},
            {"slot_key": "C", "display_name": "Center", "count": 1, "sort_order": 5},
            {"slot_key": "G", "display_name": "Guard", "count": 1, "sort_order": 6},
            {"slot_key": "F", "display_name": "Forward", "count": 1, "sort_order": 7},
            {"slot_key": "UTIL", "display_name": "Utility", "count": 1, "sort_order": 8},
            {"slot_key": "BE", "display_name": "Bench", "count": 1, "sort_order": 9},
            {"slot_key": "IR", "display_name": "Injured Reserve", "count": 2, "sort_order": 10},
        ],
    }


async def run_seed(seed_module, seed_function, session_factory):
    original_session_factory = seed_module.AsyncSessionLocal
    seed_module.AsyncSessionLocal = session_factory
    try:
        return await seed_function()
    finally:
        seed_module.AsyncSessionLocal = original_session_factory


async def run_standard_seed_workflow(client: AsyncClient) -> tuple[int, int, int, int]:
    from app.drafts import seed as draft_seed_module
    from app.leagues import seed as league_seed_module
    from app.players import seed as player_seed_module
    from app.projections import seed as projection_seed_module

    session_factory = client.session_factory
    return (
        await run_seed(player_seed_module, seed_players, session_factory),
        await run_seed(league_seed_module, seed_league, session_factory),
        await run_seed(projection_seed_module, seed_projections, session_factory),
        await run_seed(draft_seed_module, seed_draft_eligibilities, session_factory),
    )


async def seed_valuation_pool(client: AsyncClient) -> None:
    assert (await client.put("/league", json=league_payload())).status_code == 200
    async with client.session_factory() as session:
        source = ProjectionSource(key="test", name="Test Projections", is_active=True)
        session.add(source)
        await session.flush()
        projection_set = ProjectionSet(
            source_id=source.id,
            name="Test 2026 Season",
            season=2026,
            projection_type="season",
            as_of_date=date(2026, 7, 24),
            is_active=True,
        )
        session.add(projection_set)
        await session.flush()

        fixtures = [
            (1, "Alpha Guard", "PG", ("PG", "SG"), Decimal("125")),
            (2, "Bravo PG", "PG", ("PG",), Decimal("110")),
            (3, "Charlie PG", "PG", ("PG",), Decimal("105")),
            (4, "Delta PG", "PG", ("PG",), Decimal("80")),
            (5, "Echo PG", "PG", ("PG",), Decimal("70")),
            (6, "Foxtrot SG", "SG", ("SG",), Decimal("108")),
            (7, "Golf SG", "SG", ("SG",), Decimal("103")),
            (8, "Hotel SG", "SG", ("SG",), Decimal("79")),
            (9, "India SG", "SG", ("SG",), Decimal("69")),
            (10, "Juliet SF", "SF", ("SF",), Decimal("107")),
            (11, "Kilo SF", "SF", ("SF",), Decimal("102")),
            (12, "Lima SF", "SF", ("SF",), Decimal("78")),
            (13, "Mike SF", "SF", ("SF",), Decimal("68")),
            (14, "November PF", "PF", ("PF",), Decimal("106")),
            (15, "Oscar PF", "PF", ("PF",), Decimal("101")),
            (16, "Papa PF", "PF", ("PF",), Decimal("77")),
            (17, "Quebec PF", "PF", ("PF",), Decimal("67")),
            (18, "Romeo C", "C", ("C",), Decimal("104")),
            (19, "Sierra C", "C", ("C",), Decimal("99")),
            (20, "Tango C", "C", ("C",), Decimal("76")),
            (21, "Uniform C", "C", ("C",), Decimal("66")),
            (22, "Mystery Projection", None, tuple(), Decimal("115")),
        ]
        for player_id, name, primary_position, positions, total in fixtures:
            session.add(
                Player(
                    id=player_id,
                    full_name=name,
                    team="TST",
                    primary_position=primary_position,
                    is_active=True,
                )
            )
            await session.flush()
            for position_key in positions:
                session.add(PlayerEligibility(player_id=player_id, position_key=position_key))
            session.add(
                PlayerProjection(
                    projection_set_id=projection_set.id,
                    player_id=player_id,
                    games=Decimal("1.00"),
                    minutes_per_game=Decimal("20.00"),
                    fgm=total,
                    fga=total,
                    ftm=Decimal("0.000"),
                    fta=Decimal("0.000"),
                    rebounds=Decimal("0.000"),
                    assists=Decimal("0.000"),
                    steals=Decimal("0.000"),
                    blocks=Decimal("0.000"),
                    turnovers=Decimal("0.000"),
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_replacement_levels_use_active_slots_and_drafted_target(
    client: AsyncClient,
) -> None:
    await seed_valuation_pool(client)

    response = await client.get("/valuations/replacement-levels")

    assert response.status_code == 200
    body = response.json()
    assert body["total_active_demand"] == 16
    assert body["drafted_player_target"] == 18
    assert {"slot_key": "BE", "count": 2} not in body["active_slot_demand"]
    assert {item["position"] for item in body["positions"]} == {"PG", "SG", "SF", "PF", "C"}


@pytest.mark.asyncio
async def test_list_valuations_returns_vor_ranks_and_decimal_strings(
    client: AsyncClient,
) -> None:
    await seed_valuation_pool(client)

    response = await client.get("/valuations", params={"sort": "overall_rank"})

    assert response.status_code == 200
    body = response.json()
    alpha = body["items"][0]
    assert alpha["player_name"] == "Alpha Guard"
    assert alpha["overall_rank"] == 1
    assert alpha["best_value_position"] in {"PG", "SG"}
    assert isinstance(alpha["projected_fantasy_points"], str)
    assert alpha["overall_vor"] is not None
    mystery = next(item for item in body["items"] if item["player_name"] == "Mystery Projection")
    assert mystery["eligible_positions"] == []
    assert mystery["position_values"] == []
    assert mystery["overall_vor"] is None
    assert mystery["best_value_position"] is None
    assert mystery["overall_rank"] is None


@pytest.mark.asyncio
async def test_filters_and_pagination_do_not_recalculate_ranks(client: AsyncClient) -> None:
    await seed_valuation_pool(client)

    unfiltered = (await client.get("/valuations")).json()
    bravo_rank = next(
        item["overall_rank"]
        for item in unfiltered["items"]
        if item["player_name"] == "Bravo PG"
    )
    filtered = await client.get(
        "/valuations",
        params={"position": "PG", "limit": 1, "offset": 1, "sort": "overall_rank"},
    )

    assert filtered.status_code == 200
    assert filtered.json()["total"] == 5
    ranks = [item["overall_rank"] for item in filtered.json()["items"]]
    assert ranks
    assert bravo_rank in [item["overall_rank"] for item in unfiltered["items"]]


@pytest.mark.asyncio
async def test_single_player_valuation_and_missing_player(client: AsyncClient) -> None:
    await seed_valuation_pool(client)

    response = await client.get("/players/1/valuation")
    missing = await client.get("/players/999/valuation")

    assert response.status_code == 200
    assert response.json()["player_id"] == 1
    assert missing.status_code == 404
    assert missing.json() == {"detail": "player valuation not found"}


@pytest.mark.asyncio
async def test_available_only_uses_current_draft_snapshot_and_excludes_drafted(
    client: AsyncClient,
) -> None:
    await seed_valuation_pool(client)
    create_response = await client.post(
        "/draft",
        json={
            "name": "Valuation Draft",
            "teams": [
                {"name": "One", "draft_position": 1},
                {"name": "Two", "draft_position": 2},
            ],
            "user_draft_position": 1,
        },
    )
    assert create_response.status_code == 200
    await client.post("/draft/start")
    assert (await client.post("/draft/picks", json={"player_id": 1})).status_code == 200

    response = await client.get("/valuations", params={"available_only": "true"})
    conflict = await client.get(
        "/valuations",
        params={"available_only": "true", "projection_set_id": 999},
    )

    assert response.status_code == 200
    assert all(item["player_id"] != 1 for item in response.json()["items"])
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "projection_set_id conflicts with current draft"}


@pytest.mark.asyncio
async def test_available_only_reuses_base_cache_and_keeps_drafted_filter_current(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_valuation_pool(client)
    create_response = await client.post(
        "/draft",
        json={
            "name": "Cached Valuation Draft",
            "teams": [
                {"name": "One", "draft_position": 1},
                {"name": "Two", "draft_position": 2},
            ],
            "user_draft_position": 1,
        },
    )
    assert create_response.status_code == 200
    assert (await client.post("/draft/start")).status_code == 200

    valuation_service_module._valuation_cache.clear()
    valuation_service_module._valuation_in_flight.clear()
    valuation_service_module._latest_league_configuration_fingerprints.clear()
    compute_count = 0
    original_compute = ValuationService._compute_valuation_snapshot

    async def counting_compute(self, context):
        nonlocal compute_count
        compute_count += 1
        return await original_compute(self, context)

    monkeypatch.setattr(
        ValuationService,
        "_compute_valuation_snapshot",
        counting_compute,
    )

    first = await client.get(
        "/valuations",
        params={"available_only": "true", "limit": 5, "sort": "overall_rank"},
    )
    assert first.status_code == 200
    drafted_player = first.json()["items"][0]
    assert compute_count == 1

    assert (
        await client.post("/draft/picks", json={"player_id": drafted_player["player_id"]})
    ).status_code == 200

    after_pick = await client.get(
        "/valuations",
        params={"available_only": "true", "search": drafted_player["player_name"]},
    )
    assert after_pick.status_code == 200
    assert after_pick.json()["total"] == 0
    assert compute_count == 1

    assert (await client.delete("/draft/picks/latest")).status_code == 200
    after_undo = await client.get(
        "/valuations",
        params={"available_only": "true", "search": drafted_player["player_name"]},
    )
    assert after_undo.status_code == 200
    assert after_undo.json()["total"] == 1
    assert compute_count == 1

    before_scoring_change = after_undo.json()["items"][0]["projected_fantasy_points"]
    async with client.session_factory() as session:
        scoring_rule = await session.scalar(
            text("SELECT id FROM scoring_rules WHERE stat_key = 'FGM'")
        )
        rule = await session.get(ScoringRule, scoring_rule)
        assert rule is not None
        original_points = rule.points
        rule.points = rule.points + Decimal("1.00")
        await session.commit()

    after_scoring_change = await client.get(
        "/valuations",
        params={"available_only": "true", "search": drafted_player["player_name"]},
    )
    assert after_scoring_change.status_code == 200
    assert after_scoring_change.json()["total"] == 1
    assert (
        after_scoring_change.json()["items"][0]["projected_fantasy_points"]
        != before_scoring_change
    )
    assert compute_count == 2

    async with client.session_factory() as session:
        rule = await session.get(ScoringRule, scoring_rule)
        assert rule is not None
        rule.points = original_points
        await session.commit()

    after_scoring_restore = await client.get(
        "/valuations",
        params={"available_only": "true", "search": drafted_player["player_name"]},
    )
    assert after_scoring_restore.status_code == 200
    assert after_scoring_restore.json()["total"] == 1
    assert (
        after_scoring_restore.json()["items"][0]["projected_fantasy_points"]
        == before_scoring_change
    )
    assert compute_count == 3


@pytest.mark.asyncio
async def test_available_only_requires_current_noncompleted_draft(client: AsyncClient) -> None:
    await seed_valuation_pool(client)

    response = await client.get("/valuations", params={"available_only": "true"})

    assert response.status_code == 409
    assert response.json() == {"detail": "draft required"}


@pytest.mark.asyncio
async def test_league_settings_locked_only_by_active_draft(client: AsyncClient) -> None:
    await seed_valuation_pool(client)
    assert (
        await client.post(
            "/draft",
            json={
                "name": "Lock Draft",
                "teams": [
                    {"name": "One", "draft_position": 1},
                    {"name": "Two", "draft_position": 2},
                ],
                "user_draft_position": 1,
            },
        )
    ).status_code == 200

    locked = await client.put("/league", json=league_payload())
    assert locked.status_code == 409
    assert locked.json() == {
        "detail": "league configuration is locked while a draft is active"
    }

    assert (await client.delete("/draft")).status_code == 204
    unlocked = await client.put("/league", json=league_payload())
    assert unlocked.status_code == 200


def test_optimizer_is_exact_not_single_pass_greedy() -> None:
    candidates = [
        ValuationCandidate(1, "Multi", Decimal("100"), Decimal("100"), ("PG", "SG")),
        ValuationCandidate(2, "Point", Decimal("99"), Decimal("99"), ("PG",)),
        ValuationCandidate(3, "Wing", Decimal("1"), Decimal("1"), ("SG",)),
        ValuationCandidate(4, "Replacement PG", Decimal("0"), Decimal("0"), ("PG",)),
        ValuationCandidate(5, "Replacement SG", Decimal("0"), Decimal("0"), ("SG",)),
        ValuationCandidate(6, "SF A", Decimal("10"), Decimal("10"), ("SF",)),
        ValuationCandidate(7, "SF B", Decimal("9"), Decimal("9"), ("SF",)),
        ValuationCandidate(8, "PF A", Decimal("10"), Decimal("10"), ("PF",)),
        ValuationCandidate(9, "PF B", Decimal("9"), Decimal("9"), ("PF",)),
        ValuationCandidate(10, "C A", Decimal("10"), Decimal("10"), ("C",)),
        ValuationCandidate(11, "C B", Decimal("9"), Decimal("9"), ("C",)),
    ]

    _, _, _, assigned = calculate_replacement_levels(
        candidates=candidates,
        roster_slot_counts={"PG": 1, "SG": 1, "SF": 1, "PF": 1, "C": 1},
        team_count=1,
    )

    assert {1, 2}.issubset(assigned)


@pytest.mark.asyncio
async def test_standard_development_seed_workflow_supports_valuations(
    client: AsyncClient,
) -> None:
    first_counts = await run_standard_seed_workflow(client)

    async with client.session_factory() as session:
        projection_set_id = await session.scalar(
            text(
                "SELECT ps.id FROM projection_sets ps "
                "JOIN projection_sources src ON src.id = ps.source_id "
                "WHERE src.key = 'manual'"
            )
        )
        session.add(
            Player(
                id=999999,
                full_name="Unrelated Seed Survivor",
                team="FA",
                primary_position="C",
                is_active=True,
            )
        )
        await session.flush()
        session.add(PlayerEligibility(player_id=999999, position_key="C"))
        session.add(
            PlayerProjection(
                projection_set_id=projection_set_id,
                player_id=999999,
                games=Decimal("10.00"),
                minutes_per_game=Decimal("10.00"),
                fgm=Decimal("1.000"),
                fga=Decimal("1.000"),
                ftm=Decimal("0.000"),
                fta=Decimal("0.000"),
                rebounds=Decimal("1.000"),
                assists=Decimal("1.000"),
                steals=Decimal("0.000"),
                blocks=Decimal("0.000"),
                turnovers=Decimal("0.000"),
            )
        )
        await session.commit()

    second_counts = await run_standard_seed_workflow(client)

    assert first_counts == second_counts
    assert first_counts[0] == len(DEVELOPMENT_PLAYER_FIXTURES)
    assert first_counts[2] == len(DEVELOPMENT_PLAYER_FIXTURES)

    async with client.session_factory() as session:
        player_count = await session.scalar(text("SELECT count(*) FROM players"))
        projection_count = await session.scalar(
            text("SELECT count(*) FROM player_projections")
        )
        eligibility_count = await session.scalar(
            text("SELECT count(*) FROM player_eligibilities")
        )
        position_counts = dict(
            (
                await session.execute(
                    text(
                        "SELECT position_key, count(*) "
                        "FROM player_eligibilities GROUP BY position_key"
                    )
                )
            ).all()
        )
        unrelated_projection = await session.scalar(
            text("SELECT count(*) FROM player_projections WHERE player_id = 999999")
        )

    expected_eligibilities = sum(
        len(fixture.eligible_positions) for fixture in DEVELOPMENT_PLAYER_FIXTURES
    )
    assert player_count == len(DEVELOPMENT_PLAYER_FIXTURES) + 1
    assert projection_count == len(DEVELOPMENT_PLAYER_FIXTURES) + 1
    assert eligibility_count == expected_eligibilities + 1
    assert unrelated_projection == 1
    assert set(position_counts) == {"PG", "SG", "SF", "PF", "C"}
    assert all(count >= 25 for count in position_counts.values())

    valuations = await client.get("/valuations")
    replacement = await client.get("/valuations/replacement-levels")
    shai = await client.get("/players/2/valuation")

    assert valuations.status_code == 200
    assert valuations.json()["total"] >= len(DEVELOPMENT_PLAYER_FIXTURES)
    assert any(item["overall_rank"] for item in valuations.json()["items"])
    assert any(
        len(item["eligible_positions"]) > 1 for item in valuations.json()["items"]
    )
    assert replacement.status_code == 200
    assert {item["position"] for item in replacement.json()["positions"]} == {
        "PG",
        "SG",
        "SF",
        "PF",
        "C",
    }
    assert all(item["replacement_player_id"] for item in replacement.json()["positions"])
    assert shai.status_code == 200
    assert shai.json()["position_values"]

    draft_response = await client.post(
        "/draft",
        json={
            "name": "Seed Workflow Draft",
            "teams": [
                {"name": f"Team {position}", "draft_position": position}
                for position in range(1, 13)
            ],
            "user_draft_position": 1,
        },
    )
    assert draft_response.status_code == 200
    assert (await client.post("/draft/start")).status_code == 200

    available_before = await client.get("/valuations", params={"available_only": "true"})
    first_player_id = available_before.json()["items"][0]["player_id"]
    assert available_before.status_code == 200
    assert available_before.json()["total"] >= 168

    assert (await client.post("/draft/picks", json={"player_id": first_player_id})).status_code == 200
    available_after_pick = await client.get("/valuations", params={"available_only": "true"})
    assert all(
        item["player_id"] != first_player_id
        for item in available_after_pick.json()["items"]
    )
    assert (await client.delete("/draft/picks/latest")).status_code == 200
    available_after_undo = await client.get(
        "/valuations",
        params={"available_only": "true", "search": available_before.json()["items"][0]["player_name"]},
    )
    assert available_after_undo.json()["total"] == 1
    assert (await client.delete("/draft")).status_code == 204
