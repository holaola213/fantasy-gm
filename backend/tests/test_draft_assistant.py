from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.draft_assistant.roster_assignment import RosterPlayer, assign_roster
from app.drafts.model import DraftPick
from app.drafts.seed import seed_draft_eligibilities
from app.leagues.seed import seed_league
from app.main import app
from app.players.model import Player, PlayerEligibility
from app.players.seed import seed_players
from app.projections.model import PlayerProjection
from app.projections.seed import seed_projections
from app.shared.config.settings import get_settings
from app.shared.database.base import Base
from app.shared.database.session import get_session


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


async def run_seed(seed_module, seed_function, session_factory):
    original_session_factory = seed_module.AsyncSessionLocal
    seed_module.AsyncSessionLocal = session_factory
    try:
        return await seed_function()
    finally:
        seed_module.AsyncSessionLocal = original_session_factory


async def seed_standard_fixtures(client: AsyncClient) -> None:
    from app.drafts import seed as draft_seed_module
    from app.leagues import seed as league_seed_module
    from app.players import seed as player_seed_module
    from app.projections import seed as projection_seed_module

    session_factory = client.session_factory
    await run_seed(player_seed_module, seed_players, session_factory)
    await run_seed(league_seed_module, seed_league, session_factory)
    await run_seed(projection_seed_module, seed_projections, session_factory)
    await run_seed(draft_seed_module, seed_draft_eligibilities, session_factory)


def draft_payload(user_position: int = 1) -> dict:
    return {
        "name": "Assistant Test Draft",
        "teams": [
            {"name": f"Team {position}", "draft_position": position}
            for position in range(1, 13)
        ],
        "user_draft_position": user_position,
    }


async def create_started_draft(client: AsyncClient, user_position: int = 1) -> dict:
    create_response = await client.post("/draft", json=draft_payload(user_position))
    assert create_response.status_code == 200
    start_response = await client.post("/draft/start")
    assert start_response.status_code == 200
    return start_response.json()


@pytest.mark.asyncio
async def test_assistant_requires_in_progress_draft(client: AsyncClient) -> None:
    response = await client.get("/draft/assistant")
    assert response.status_code == 409
    assert response.json() == {"detail": "active draft required"}

    await seed_standard_fixtures(client)
    assert (await client.post("/draft", json=draft_payload())).status_code == 200
    setup_response = await client.get("/draft/assistant")
    assert setup_response.status_code == 409
    assert setup_response.json() == {"detail": "active draft required"}


@pytest.mark.asyncio
async def test_empty_roster_assistant_returns_context_and_options(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)

    response = await client.get("/draft/assistant")

    assert response.status_code == 200
    body = response.json()
    assert body["current_overall_pick"] == 1
    assert body["is_user_on_clock"] is True
    assert body["roster_summary"]["active_slots_total"] == 10
    assert body["roster_summary"]["active_slots_filled"] == 0
    assert body["roster_summary"]["active_slots_unfilled"] == 10
    assert body["roster_summary"]["bench_slots_total"] == 4
    assert body["user_team"]["roster_spots_remaining"] == 14
    assert len(body["best_available"]) == 5
    assert [section["position"] for section in body["best_by_position"]] == [
        "PG",
        "SG",
        "SF",
        "PF",
        "C",
    ]
    assert len(body["roster_fit_options"]) == 5
    assert body["best_available"][0]["reasons"] == [{"code": "BEST_AVAILABLE", "position": None, "slots": []}]


@pytest.mark.asyncio
async def test_assistant_available_when_another_team_is_on_clock(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=4)

    response = await client.get("/draft/assistant")

    assert response.status_code == 200
    assert response.json()["is_user_on_clock"] is False
    assert response.json()["on_clock_team"]["draft_position"] == 1


@pytest.mark.asyncio
async def test_pick_and_undo_update_assistant_available_players(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)
    before = (await client.get("/draft/assistant")).json()
    player_id = before["best_available"][0]["player_id"]

    pick_response = await client.post("/draft/picks", json={"player_id": player_id})
    assert pick_response.status_code == 200
    after_pick = (await client.get("/draft/assistant")).json()
    assert after_pick["roster_summary"]["players_drafted"] == 1
    assert all(item["player_id"] != player_id for item in after_pick["best_available"])

    undo_response = await client.delete("/draft/picks/latest")
    assert undo_response.status_code == 200
    after_undo = (await client.get("/draft/assistant")).json()
    assert after_undo["roster_summary"]["players_drafted"] == 0
    assert after_undo["best_available"][0]["player_id"] == player_id


@pytest.mark.asyncio
async def test_second_round_snake_pick_is_in_user_roster_summary(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)

    for _ in range(24):
        assistant = (await client.get("/draft/assistant")).json()
        pick_response = await client.post(
            "/draft/picks",
            json={"player_id": assistant["best_available"][0]["player_id"]},
        )
        assert pick_response.status_code == 200

    board = (await client.get("/draft/board")).json()
    user_team = next(team for team in board["teams"] if team["is_user_team"])
    user_picks = [
        pick for pick in board["picks"] if pick["fantasy_team_id"] == user_team["id"]
    ]
    assert [pick["overall_pick"] for pick in user_picks] == [1, 24]

    assistant = (await client.get("/draft/assistant")).json()
    summary = assistant["roster_summary"]
    represented = [
        *summary["assignments"],
        *summary["bench_assignments"],
        *summary["unassigned_players"],
    ]

    assert assistant["user_team"]["players_drafted"] == 2
    assert summary["players_drafted"] == 2
    assert len(represented) == 2
    assert {player["player_id"] for player in represented} == {
        pick["player_id"] for pick in user_picks
    }


@pytest.mark.asyncio
async def test_roster_fits_use_open_slots_and_structured_reasons(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)
    await client.post("/draft/picks", json={"player_id": 1})

    response = await client.get("/draft/assistant", params={"limit_per_section": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["roster_summary"]["active_slots_filled"] == 1
    assert not any(
        slot["slot"] == "C" and slot["slot_index"] == 1
        for slot in body["roster_summary"]["unfilled_slots"]
    )
    fit = body["roster_fit_options"][0]
    reason_codes = {reason["code"] for reason in fit["reasons"]}
    assert "FILLS_OPEN_SLOT" in reason_codes
    assert fit["matching_open_slots"]


@pytest.mark.asyncio
async def test_best_by_position_uses_position_specific_values(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)

    response = await client.get("/draft/assistant")

    assert response.status_code == 200
    section = next(
        item for item in response.json()["best_by_position"] if item["position"] == "PG"
    )
    assert section["items"]
    assert section["items"][0]["position"] == "PG"
    assert section["items"][0]["position_rank"] is not None
    assert section["items"][0]["position_vor"] is not None
    assert section["items"][0]["reasons"][0]["code"] == "BEST_AT_POSITION"


@pytest.mark.asyncio
async def test_include_assignments_false_keeps_counts_and_open_slots(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)
    await client.post("/draft/picks", json={"player_id": 1})

    response = await client.get(
        "/draft/assistant",
        params={"include_assignments": "false"},
    )

    assert response.status_code == 200
    summary = response.json()["roster_summary"]
    assert summary["active_slots_filled"] == 1
    assert summary["assignments"] == []
    assert summary["bench_assignments"] == []
    assert summary["unassigned_players"] == []
    assert summary["unfilled_slots"]


@pytest.mark.asyncio
async def test_missing_user_team_returns_safe_conflict(client: AsyncClient) -> None:
    await seed_standard_fixtures(client)
    draft = await create_started_draft(client, user_position=1)

    async with client.session_factory() as session:
        await session.execute(
            text("UPDATE fantasy_teams SET is_user_team = false WHERE draft_session_id = :id"),
            {"id": draft["id"]},
        )
        await session.commit()

    response = await client.get("/draft/assistant")

    assert response.status_code == 409
    assert response.json() == {"detail": "user fantasy team required"}


@pytest.mark.asyncio
async def test_drafted_player_without_eligibility_is_unassigned(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    draft = await create_started_draft(client, user_position=1)

    async with client.session_factory() as session:
        session.add(
            Player(
                full_name="No Eligibility Assistant Player",
                team="FA",
                primary_position="PG",
                is_active=True,
            )
        )
        await session.flush()
        player_id = await session.scalar(
            text("SELECT id FROM players WHERE full_name = 'No Eligibility Assistant Player'")
        )
        session.add(
            PlayerProjection(
                projection_set_id=draft["projection_set_id"],
                player_id=player_id,
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
        user_team_id = await session.scalar(
            text(
                "SELECT id FROM fantasy_teams "
                "WHERE draft_session_id = :draft_id AND is_user_team = true"
            ),
            {"draft_id": draft["id"]},
        )
        session.add(
            DraftPick(
                draft_session_id=draft["id"],
                fantasy_team_id=user_team_id,
                player_id=player_id,
                round_number=1,
                pick_in_round=1,
                overall_pick=1,
            )
        )
        await session.commit()

    response = await client.get("/draft/assistant")

    assert response.status_code == 200
    unassigned = response.json()["roster_summary"]["unassigned_players"]
    assert unassigned[0]["player_name"] == "No Eligibility Assistant Player"
    assert unassigned[0]["reason"] == "missing eligibility"


@pytest.mark.asyncio
async def test_completed_draft_returns_active_draft_required(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    draft = await create_started_draft(client, user_position=1)

    async with client.session_factory() as session:
        await session.execute(
            text(
                "UPDATE draft_sessions SET status = 'completed', completed_at = :now "
                "WHERE id = :id"
            ),
            {"id": draft["id"], "now": datetime.now(UTC)},
        )
        await session.commit()

    response = await client.get("/draft/assistant")

    assert response.status_code == 409
    assert response.json() == {"detail": "active draft required"}


def test_assignment_preserves_flexibility_for_restrictive_slots() -> None:
    result = assign_roster(
        players=[
            RosterPlayer(
                draft_pick_id=1,
                player_id=1,
                player_name="Point Only",
                eligible_positions=("PG",),
                projected_fantasy_points=Decimal("100.00"),
                overall_pick=1,
            ),
            RosterPlayer(
                draft_pick_id=2,
                player_id=2,
                player_name="Guard Flex",
                eligible_positions=("PG", "SG"),
                projected_fantasy_points=Decimal("100.00"),
                overall_pick=2,
            ),
            RosterPlayer(
                draft_pick_id=3,
                player_id=3,
                player_name="Shooting Only",
                eligible_positions=("SG",),
                projected_fantasy_points=Decimal("100.00"),
                overall_pick=3,
            ),
        ],
        roster_slot_counts={"PG": 1, "SG": 1, "G": 1, "BE": 0},
    )

    assignments = {
        assignment.slot.slot: assignment.player.player_name
        for assignment in result.active_assignments
    }
    assert assignments == {
        "PG": "Point Only",
        "SG": "Shooting Only",
        "G": "Guard Flex",
    }


def test_assignment_prefers_active_points_before_bench_order() -> None:
    result = assign_roster(
        players=[
            RosterPlayer(
                draft_pick_id=1,
                player_id=1,
                player_name="Earlier Bench",
                eligible_positions=("PG",),
                projected_fantasy_points=Decimal("10.00"),
                overall_pick=1,
            ),
            RosterPlayer(
                draft_pick_id=2,
                player_id=2,
                player_name="Later Active",
                eligible_positions=("PG",),
                projected_fantasy_points=Decimal("20.00"),
                overall_pick=2,
            ),
        ],
        roster_slot_counts={"PG": 1, "BE": 1},
    )

    assert result.active_assignments[0].player.player_name == "Later Active"
    assert result.bench_assignments[0].player.player_name == "Earlier Bench"
