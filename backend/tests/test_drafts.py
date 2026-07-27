from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.drafts.compatibility import (
    calculate_draft_rounds,
    compatible_roster_slots,
    snake_pick_details,
)
from app.drafts.model import DraftPick, DraftSession, FantasyTeam
from app.drafts.seed import seed_draft_eligibilities
from app.main import app
from app.players.model import Player, PlayerEligibility
from app.players.seed import seed_players
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
            test_client.session_factory = session_factory
            yield test_client
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await engine.dispose()


async def run_seed(seed_module, seed_function, session_factory):
    original_session_factory = seed_module.AsyncSessionLocal
    seed_module.AsyncSessionLocal = session_factory
    try:
        return await seed_function()
    finally:
        seed_module.AsyncSessionLocal = original_session_factory


async def seed_core_fixtures(client: AsyncClient) -> None:
    from app.drafts import seed as draft_seed_module
    from app.leagues import seed as league_seed_module
    from app.leagues.seed import seed_league
    from app.players import seed as player_seed_module
    from app.projections import seed as projection_seed_module

    session_factory = client.session_factory
    await run_seed(player_seed_module, seed_players, session_factory)
    await run_seed(league_seed_module, seed_league, session_factory)
    await run_seed(projection_seed_module, seed_projections, session_factory)
    await run_seed(draft_seed_module, seed_draft_eligibilities, session_factory)


def draft_payload(team_count: int = 12, user_position: int = 4) -> dict:
    return {
        "name": "2026 League Draft",
        "teams": [
            {"name": f" Team {position} ", "draft_position": position}
            for position in range(1, team_count + 1)
        ],
        "user_draft_position": user_position,
    }


def small_league_payload() -> dict:
    return {
        "name": "Two Team Test League",
        "platform": "ESPN",
        "season": 2026,
        "team_count": 2,
        "scoring_format": "points",
        "acquisition_limit_per_day": 1,
        "playoff_team_count": 2,
        "scoring_rules": [
            {"stat_key": "FGM", "display_name": "Field Goals Made", "points": 1, "sort_order": 1},
            {"stat_key": "REB", "display_name": "Rebounds", "points": 1, "sort_order": 2},
            {"stat_key": "PTS", "display_name": "Points", "points": 1, "sort_order": 3},
            {"stat_key": "TEAM_WINS", "display_name": "Team Wins", "points": 1, "sort_order": 4},
        ],
        "roster_slots": [
            {"slot_key": "PG", "display_name": "Point Guard", "count": 1, "sort_order": 1},
            {"slot_key": "IR", "display_name": "Injured Reserve", "count": 2, "sort_order": 2},
        ],
    }


def test_slot_compatibility_and_snake_order_helpers() -> None:
    assert compatible_roster_slots(["PG", "SG"], ["PG", "SG", "G", "UTIL", "BE", "IR"]) == [
        "PG",
        "SG",
        "G",
        "UTIL",
        "BE",
    ]
    assert calculate_draft_rounds(
        {"PG": 1, "SG": 1, "SF": 1, "PF": 1, "C": 1, "G": 1, "F": 1, "UTIL": 3, "BE": 4, "IR": 2}
    ) == 14
    assert snake_pick_details(1, 12) == (1, 1, 1)
    assert snake_pick_details(12, 12) == (1, 12, 12)
    assert snake_pick_details(13, 12) == (2, 1, 12)
    assert snake_pick_details(24, 12) == (2, 12, 1)
    assert snake_pick_details(25, 12) == (3, 1, 1)


@pytest.mark.asyncio
async def test_eligibility_seed_is_idempotent_and_preserves_unrelated_rows(
    client: AsyncClient,
) -> None:
    from app.drafts import seed as draft_seed_module
    from app.players import seed as player_seed_module

    await run_seed(player_seed_module, seed_players, client.session_factory)
    expected_eligibilities = sum(
        len(fixture.eligible_positions) for fixture in DEVELOPMENT_PLAYER_FIXTURES
    )
    assert (
        await run_seed(
            draft_seed_module,
            seed_draft_eligibilities,
            client.session_factory,
        )
        == expected_eligibilities
    )

    async with client.session_factory() as session:
        session.add(Player(id=999, full_name="Unrelated Player", is_active=True))
        await session.flush()
        session.add(PlayerEligibility(player_id=999, position_key="C"))
        await session.commit()

    assert (
        await run_seed(
            draft_seed_module,
            seed_draft_eligibilities,
            client.session_factory,
        )
        == expected_eligibilities
    )

    async with client.session_factory() as session:
        total = await session.scalar(text("SELECT count(*) FROM player_eligibilities"))
        unrelated = await session.scalar(
            text("SELECT position_key FROM player_eligibilities WHERE player_id = 999")
        )

    assert total == expected_eligibilities + 1
    assert unrelated == "C"


@pytest.mark.asyncio
async def test_eligibility_seed_fails_when_player_fixtures_are_missing(
    client: AsyncClient,
) -> None:
    from app.drafts import seed as draft_seed_module

    with pytest.raises(RuntimeError, match="missing players"):
        await run_seed(draft_seed_module, seed_draft_eligibilities, client.session_factory)


@pytest.mark.asyncio
async def test_create_draft_snapshots_projection_set_and_calculates_rounds(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)

    response = await client.post("/draft", json=draft_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["league_id"] == 1
    assert body["projection_set_id"] == 1
    assert body["team_count"] == 12
    assert body["rounds"] == 14
    assert body["current_pick_number"] == 1
    assert body["current_round"] == 1
    assert body["current_pick_in_round"] == 1

    board = (await client.get("/draft/board")).json()
    assert len(board["teams"]) == 12
    assert board["teams"][3]["is_user_team"] is True
    assert board["teams"][0]["name"] == "Team 1"


@pytest.mark.asyncio
async def test_create_draft_requires_league_and_active_projection_set(
    client: AsyncClient,
) -> None:
    missing_league_response = await client.post("/draft", json=draft_payload())
    assert missing_league_response.status_code == 409
    assert missing_league_response.json() == {"detail": "league configuration required"}

    from app.leagues import seed as league_seed_module
    from app.leagues.seed import seed_league

    await run_seed(league_seed_module, seed_league, client.session_factory)
    missing_projection_response = await client.post("/draft", json=draft_payload())
    assert missing_projection_response.status_code == 409
    assert missing_projection_response.json() == {"detail": "active projection set required"}


@pytest.mark.asyncio
async def test_setup_is_editable_only_until_start_and_one_current_draft_is_allowed(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    assert (await client.post("/draft", json=draft_payload())).status_code == 200

    duplicate_response = await client.post("/draft", json=draft_payload())
    assert duplicate_response.status_code == 409

    update_payload = draft_payload()
    update_payload["teams"][0]["name"] = " Renamed Team "
    update_response = await client.put("/draft/setup", json=update_payload)
    assert update_response.status_code == 200
    teams = (await client.get("/draft/teams")).json()
    assert teams[0]["name"] == "Renamed Team"

    start_response = await client.post("/draft/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"

    frozen_response = await client.put("/draft/setup", json=update_payload)
    assert frozen_response.status_code == 409
    assert frozen_response.json() == {"detail": "draft must be in setup"}


@pytest.mark.asyncio
async def test_available_players_use_draft_projection_set_filters_and_sorting(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    await client.post("/draft", json=draft_payload())

    response = await client.get(
        "/draft/available-players",
        params={"position": "PG", "sort": "player", "direction": "asc", "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    assert len({item["player_id"] for item in body["items"]}) == len(body["items"])
    assert len(body["items"]) == 2
    assert body["items"][0]["eligible_positions"]
    assert "UTIL" in body["items"][0]["compatible_roster_slots"]

    fantasy_response = await client.get(
        "/draft/available-players",
        params={"sort": "projected_fantasy_points", "direction": "desc", "limit": 1},
    )
    assert fantasy_response.status_code == 200
    assert fantasy_response.json()["items"][0]["full_name"] == "Nikola Jokic"


@pytest.mark.asyncio
async def test_available_players_keep_draft_projection_snapshot(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    create_response = await client.post("/draft", json=draft_payload())
    assert create_response.status_code == 200
    snapshotted_projection_set_id = create_response.json()["projection_set_id"]

    async with client.session_factory() as session:
        source = ProjectionSource(
            key="late-manual",
            name="Later Manual Projections",
            is_active=True,
        )
        session.add(source)
        await session.flush()
        later_set = ProjectionSet(
            source_id=source.id,
            name="Later Active Set",
            season=2026,
            projection_type="season",
            as_of_date=date(2026, 7, 25),
            is_active=True,
        )
        session.add(later_set)
        await session.flush()
        session.add(Player(id=999, full_name="Later Only Player", team="FA", is_active=True))
        await session.flush()
        session.add(PlayerEligibility(player_id=999, position_key="PG"))
        session.add(
            PlayerProjection(
                projection_set_id=later_set.id,
                player_id=999,
                games=Decimal("70.00"),
                minutes_per_game=Decimal("20.00"),
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
        await session.commit()

    draft_response = await client.get("/draft")
    assert draft_response.json()["projection_set_id"] == snapshotted_projection_set_id
    available_response = await client.get(
        "/draft/available-players",
        params={"search": "Later Only"},
    )
    assert available_response.status_code == 200
    assert available_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_available_players_have_deterministic_tie_sorting(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    async with client.session_factory() as session:
        await session.execute(
            text(
                "UPDATE player_projections "
                "SET fgm = 1, fga = 1, ftm = 0, fta = 0, rebounds = 0, "
                "assists = 0, steals = 0, blocks = 0, turnovers = 0 "
                "WHERE player_id IN (2, 3)"
            )
        )
        await session.commit()

    await client.post("/draft", json=draft_payload())
    response = await client.get(
        "/draft/available-players",
        params={
            "position": "PG",
            "sort": "fantasy_points_per_game",
            "direction": "desc",
        },
    )

    assert response.status_code == 200
    tied_names = [
        item["full_name"]
        for item in response.json()["items"]
        if item["full_name"] in {"Luka Doncic", "Shai Gilgeous-Alexander"}
    ]
    assert tied_names == ["Luka Doncic", "Shai Gilgeous-Alexander"]


@pytest.mark.asyncio
async def test_picks_are_sequential_and_exclude_drafted_players(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    await client.post("/draft", json=draft_payload())
    await client.post("/draft/start")

    pick_response = await client.post("/draft/picks", json={"player_id": 1})
    assert pick_response.status_code == 200
    body = pick_response.json()
    assert body["overall_pick"] == 1
    assert body["round_number"] == 1
    assert body["pick_in_round"] == 1
    assert body["fantasy_team_name"] == "Team 1"

    duplicate_response = await client.post("/draft/picks", json={"player_id": 1})
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {"detail": "player unavailable"}

    available = await client.get("/draft/available-players", params={"search": "jokic"})
    assert available.status_code == 200
    assert available.json()["total"] == 0


@pytest.mark.asyncio
async def test_reset_in_progress_draft_preserves_setup_and_clears_picks(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    create_response = await client.post("/draft", json=draft_payload(user_position=4))
    await client.post("/draft/start")
    for player_id in [1, 2, 3, 4, 5]:
        assert (await client.post("/draft/picks", json={"player_id": player_id})).status_code == 200

    before_board = (await client.get("/draft/board")).json()
    before_teams = before_board["teams"]
    reset_response = await client.post("/draft/reset")

    assert reset_response.status_code == 200
    body = reset_response.json()
    assert body["id"] == create_response.json()["id"]
    assert body["status"] == "setup"
    assert body["projection_set_id"] == create_response.json()["projection_set_id"]
    assert body["team_count"] == create_response.json()["team_count"]
    assert body["rounds"] == create_response.json()["rounds"]
    assert body["current_pick_number"] == 1
    assert body["current_round"] == 1
    assert body["current_pick_in_round"] == 1
    assert body["started_at"] is None
    assert body["completed_at"] is None

    after_board = (await client.get("/draft/board")).json()
    assert after_board["picks"] == []
    assert [
        (team["name"], team["draft_position"], team["is_user_team"])
        for team in after_board["teams"]
    ] == [
        (team["name"], team["draft_position"], team["is_user_team"])
        for team in before_teams
    ]

    assistant_response = await client.get("/draft/assistant")
    assert assistant_response.status_code == 409
    assert assistant_response.json() == {"detail": "active draft required"}

    jokic_available = await client.get("/draft/available-players", params={"search": "jokic"})
    assert jokic_available.status_code == 200
    assert jokic_available.json()["total"] == 1


@pytest.mark.asyncio
async def test_start_after_reset_reuses_snapshot_and_restarts_at_first_pick(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    create_response = await client.post("/draft", json=draft_payload(user_position=4))
    projection_set_id = create_response.json()["projection_set_id"]
    await client.post("/draft/start")
    assert (await client.post("/draft/picks", json={"player_id": 1})).status_code == 200

    reset_response = await client.post("/draft/reset")
    assert reset_response.status_code == 200
    restarted = await client.post("/draft/start")
    assert restarted.status_code == 200
    assert restarted.json()["projection_set_id"] == projection_set_id
    assert restarted.json()["current_pick_number"] == 1

    pick_response = await client.post("/draft/picks", json={"player_id": 1})
    assert pick_response.status_code == 200
    assert pick_response.json()["overall_pick"] == 1
    assert pick_response.json()["round_number"] == 1
    assert pick_response.json()["pick_in_round"] == 1
    assert pick_response.json()["fantasy_team_name"] == "Team 1"


@pytest.mark.asyncio
async def test_api_picks_follow_snake_boundaries_and_only_latest_undo(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    await client.post("/draft", json=draft_payload())
    await client.post("/draft/start")

    picked_player_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    for player_id in picked_player_ids:
        response = await client.post("/draft/picks", json={"player_id": player_id})
        assert response.status_code == 200

    board = (await client.get("/draft/board")).json()
    picks = board["picks"]
    assert picks[0]["overall_pick"] == 1
    assert picks[0]["fantasy_team_name"] == "Team 1"
    assert picks[9]["overall_pick"] == 10
    assert picks[9]["fantasy_team_name"] == "Team 10"

    # Insert two more eligible projected players so the API can cross into round 2.
    async with client.session_factory() as session:
        for player_id, name in [
            (1001, "Boundary Player A"),
            (1002, "Boundary Player B"),
            (1003, "Boundary Player C"),
        ]:
            session.add(Player(id=player_id, full_name=name, team="FA", is_active=True))
            await session.flush()
            session.add(PlayerEligibility(player_id=player_id, position_key="PG"))
            session.add(
                PlayerProjection(
                    projection_set_id=1,
                    player_id=player_id,
                    games=Decimal("70.00"),
                    minutes_per_game=Decimal("20.00"),
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
        await session.commit()

    pick_11 = await client.post("/draft/picks", json={"player_id": 1001})
    pick_12 = await client.post("/draft/picks", json={"player_id": 1002})
    pick_13 = await client.post("/draft/picks", json={"player_id": 1003})
    assert pick_11.json()["fantasy_team_name"] == "Team 11"
    assert pick_12.json()["fantasy_team_name"] == "Team 12"
    assert pick_13.json()["round_number"] == 2
    assert pick_13.json()["pick_in_round"] == 1
    assert pick_13.json()["fantasy_team_name"] == "Team 12"

    undo_response = await client.delete("/draft/picks/latest")
    assert undo_response.status_code == 200
    assert undo_response.json()["overall_pick"] == 13
    remaining_board = (await client.get("/draft/board")).json()
    assert [pick["overall_pick"] for pick in remaining_board["picks"]][-1] == 12


@pytest.mark.asyncio
async def test_player_without_eligibility_is_available_but_cannot_be_drafted(
    client: AsyncClient,
) -> None:
    await seed_core_fixtures(client)
    await client.post("/draft", json=draft_payload())
    await client.post("/draft/start")

    async with client.session_factory() as session:
        session.add(Player(id=999, full_name="Projected Mystery", team="FA", is_active=True))
        await session.flush()
        session.add(
            PlayerProjection(
                projection_set_id=1,
                player_id=999,
                games=Decimal("70.00"),
                minutes_per_game=Decimal("20.00"),
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
        await session.commit()

    available = await client.get("/draft/available-players", params={"search": "mystery"})
    assert available.status_code == 200
    assert available.json()["items"][0]["eligible_positions"] == []
    assert available.json()["items"][0]["compatible_roster_slots"] == []

    pick_response = await client.post("/draft/picks", json={"player_id": 999})
    assert pick_response.status_code == 409
    assert pick_response.json() == {"detail": "player eligibility required"}


@pytest.mark.asyncio
async def test_final_pick_completes_draft_undo_restores_and_completed_delete_rejected(
    client: AsyncClient,
) -> None:
    from app.drafts import seed as draft_seed_module
    from app.leagues import seed as league_seed_module
    from app.players import seed as player_seed_module
    from app.projections import seed as projection_seed_module

    await run_seed(player_seed_module, seed_players, client.session_factory)
    await client.put("/league", json=small_league_payload())
    await run_seed(projection_seed_module, seed_projections, client.session_factory)
    await run_seed(draft_seed_module, seed_draft_eligibilities, client.session_factory)

    response = await client.post("/draft", json=draft_payload(team_count=2, user_position=1))
    assert response.status_code == 200
    assert response.json()["rounds"] == 1
    await client.post("/draft/start")
    assert (await client.post("/draft/picks", json={"player_id": 1})).status_code == 200
    final_pick = await client.post("/draft/picks", json={"player_id": 2})
    assert final_pick.status_code == 200

    draft = (await client.get("/draft")).json()
    assert draft["status"] == "completed"
    assert draft["current_pick_number"] is None
    delete_response = await client.delete("/draft")
    assert delete_response.status_code == 409
    assert delete_response.json() == {"detail": "completed draft cannot be deleted"}

    undo_response = await client.delete("/draft/picks/latest")
    assert undo_response.status_code == 200
    assert undo_response.json()["player_id"] == 2
    restored = (await client.get("/draft")).json()
    assert restored["status"] == "in_progress"
    assert restored["current_pick_number"] == 2

    after_completion_pick = await client.post("/draft/picks", json={"player_id": 3})
    assert after_completion_pick.status_code == 200


@pytest.mark.asyncio
async def test_completed_draft_can_be_reset(client: AsyncClient) -> None:
    from app.drafts import seed as draft_seed_module
    from app.players import seed as player_seed_module
    from app.projections import seed as projection_seed_module

    await run_seed(player_seed_module, seed_players, client.session_factory)
    await client.put("/league", json=small_league_payload())
    await run_seed(projection_seed_module, seed_projections, client.session_factory)
    await run_seed(draft_seed_module, seed_draft_eligibilities, client.session_factory)

    create_response = await client.post(
        "/draft",
        json=draft_payload(team_count=2, user_position=1),
    )
    await client.post("/draft/start")
    await client.post("/draft/picks", json={"player_id": 1})
    await client.post("/draft/picks", json={"player_id": 2})
    assert (await client.get("/draft")).json()["status"] == "completed"

    reset_response = await client.post("/draft/reset")

    assert reset_response.status_code == 200
    assert reset_response.json()["id"] == create_response.json()["id"]
    assert reset_response.json()["status"] == "setup"
    assert reset_response.json()["current_pick_number"] == 1
    assert (await client.get("/draft/board")).json()["picks"] == []


@pytest.mark.asyncio
async def test_setup_draft_reset_is_idempotent(client: AsyncClient) -> None:
    await seed_core_fixtures(client)
    create_response = await client.post("/draft", json=draft_payload(user_position=4))

    first_reset = await client.post("/draft/reset")
    second_reset = await client.post("/draft/reset")

    assert first_reset.status_code == 200
    assert second_reset.status_code == 200
    assert second_reset.json()["id"] == create_response.json()["id"]
    assert second_reset.json()["status"] == "setup"
    assert second_reset.json()["current_pick_number"] == 1
    assert (await client.get("/draft/board")).json()["picks"] == []


@pytest.mark.asyncio
async def test_reset_missing_draft_returns_not_found(client: AsyncClient) -> None:
    response = await client.post("/draft/reset")

    assert response.status_code == 404
    assert response.json() == {"detail": "draft not found"}


@pytest.mark.asyncio
async def test_pick_after_completion_is_rejected(client: AsyncClient) -> None:
    from app.drafts import seed as draft_seed_module
    from app.players import seed as player_seed_module
    from app.projections import seed as projection_seed_module

    await run_seed(player_seed_module, seed_players, client.session_factory)
    await client.put("/league", json=small_league_payload())
    await run_seed(projection_seed_module, seed_projections, client.session_factory)
    await run_seed(draft_seed_module, seed_draft_eligibilities, client.session_factory)

    await client.post("/draft", json=draft_payload(team_count=2, user_position=1))
    await client.post("/draft/start")
    await client.post("/draft/picks", json={"player_id": 1})
    await client.post("/draft/picks", json={"player_id": 2})

    response = await client.post("/draft/picks", json={"player_id": 3})
    assert response.status_code == 409
    assert response.json() == {"detail": "draft must be in progress"}


@pytest.mark.asyncio
async def test_in_progress_draft_can_be_deleted(client: AsyncClient) -> None:
    await seed_core_fixtures(client)
    await client.post("/draft", json=draft_payload())
    await client.post("/draft/start")

    response = await client.delete("/draft")

    assert response.status_code == 204
    assert (await client.get("/draft")).status_code == 404


@pytest.mark.asyncio
async def test_database_rejects_multiple_user_teams(client: AsyncClient) -> None:
    await seed_core_fixtures(client)

    async with client.session_factory() as session:
        draft = DraftSession(
            league_id=1,
            projection_set_id=1,
            name="User Team Constraint",
            season=2026,
            draft_type="snake",
            status="completed",
            team_count=2,
            rounds=1,
            completed_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add_all(
            [
                FantasyTeam(
                    draft_session_id=draft.id,
                    name="First",
                    draft_position=1,
                    is_user_team=True,
                ),
                FantasyTeam(
                    draft_session_id=draft.id,
                    name="Second",
                    draft_position=2,
                    is_user_team=True,
                ),
            ]
        )
        with pytest.raises(Exception):
            await session.commit()


@pytest.mark.asyncio
async def test_database_rejects_cross_session_team_reference(client: AsyncClient) -> None:
    await seed_core_fixtures(client)

    async with client.session_factory() as session:
        first = DraftSession(
            league_id=1,
            projection_set_id=1,
            name="First",
            season=2026,
            draft_type="snake",
            status="completed",
            team_count=2,
            rounds=1,
            completed_at=datetime.now(UTC),
        )
        second = DraftSession(
            league_id=1,
            projection_set_id=1,
            name="Second",
            season=2026,
            draft_type="snake",
            status="completed",
            team_count=2,
            rounds=1,
            completed_at=datetime.now(UTC),
        )
        session.add_all([first, second])
        await session.flush()
        first_team = FantasyTeam(
            draft_session_id=first.id,
            name="First Team",
            draft_position=1,
            is_user_team=True,
        )
        session.add(first_team)
        await session.flush()
        session.add(
            DraftPick(
                draft_session_id=second.id,
                fantasy_team_id=first_team.id,
                player_id=1,
                round_number=1,
                pick_in_round=1,
                overall_pick=1,
            )
        )
        with pytest.raises(Exception):
            await session.commit()
