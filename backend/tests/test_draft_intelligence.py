from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.draft_assistant.availability import AVAILABILITY_RISK_BUFFER
from app.draft_assistant.availability import availability_outlooks
from app.draft_assistant.scarcity import positional_scarcity
from app.draft_assistant.value_gaps import (
    MEANINGFUL_VALUE_DROP,
    VALUE_DROP_SCAN_LIMIT,
    next_meaningful_value_drop,
)
from app.drafts.order import NextUserPickContext, next_user_pick_context
from app.valuations.schemas import PlayerValuationRead, PositionValueRead
from tests.test_draft_assistant import (
    client,
    create_started_draft,
    seed_standard_fixtures,
)


def test_next_user_pick_context_handles_snake_turns() -> None:
    first_position = next_user_pick_context(
        current_overall_pick=20,
        team_count=12,
        rounds=14,
        user_draft_position=1,
    )
    assert first_position is not None
    assert first_position.next_overall_pick == 24
    assert first_position.picks_until == 4
    assert first_position.is_user_on_clock is False
    assert first_position.consecutive_pick_overalls == (24, 25)

    turn_position = next_user_pick_context(
        current_overall_pick=12,
        team_count=12,
        rounds=14,
        user_draft_position=12,
    )
    assert turn_position is not None
    assert turn_position.next_overall_pick == 12
    assert turn_position.picks_until == 0
    assert turn_position.is_user_on_clock is True
    assert turn_position.consecutive_pick_overalls == (12, 13)

    middle_position = next_user_pick_context(
        current_overall_pick=20,
        team_count=12,
        rounds=14,
        user_draft_position=6,
    )
    assert middle_position is not None
    assert middle_position.next_overall_pick == 30
    assert middle_position.picks_until == 10
    assert middle_position.is_consecutive_turn is False


def test_next_user_pick_context_handles_second_turn_picks_and_final_state() -> None:
    team_one_second_turn_pick = next_user_pick_context(
        current_overall_pick=25,
        team_count=12,
        rounds=14,
        user_draft_position=1,
    )
    assert team_one_second_turn_pick is not None
    assert team_one_second_turn_pick.next_overall_pick == 25
    assert team_one_second_turn_pick.picks_until == 0
    assert team_one_second_turn_pick.is_consecutive_turn is True
    assert team_one_second_turn_pick.turn_pick_number == 2
    assert team_one_second_turn_pick.consecutive_pick_numbers == (1, 2)
    assert team_one_second_turn_pick.consecutive_pick_overalls == (24, 25)

    team_twelve_second_turn_pick = next_user_pick_context(
        current_overall_pick=13,
        team_count=12,
        rounds=14,
        user_draft_position=12,
    )
    assert team_twelve_second_turn_pick is not None
    assert team_twelve_second_turn_pick.next_overall_pick == 13
    assert team_twelve_second_turn_pick.is_consecutive_turn is True
    assert team_twelve_second_turn_pick.turn_pick_number == 2
    assert team_twelve_second_turn_pick.consecutive_pick_overalls == (12, 13)

    final_user_pick = next_user_pick_context(
        current_overall_pick=168,
        team_count=12,
        rounds=14,
        user_draft_position=1,
    )
    assert final_user_pick is not None
    assert final_user_pick.next_overall_pick == 168
    assert final_user_pick.picks_until == 0
    assert final_user_pick.is_consecutive_turn is False

    assert (
        next_user_pick_context(
            current_overall_pick=169,
            team_count=12,
            rounds=14,
            user_draft_position=1,
        )
        is None
    )
    assert (
        next_user_pick_context(
            current_overall_pick=158,
            team_count=12,
            rounds=14,
            user_draft_position=12,
        )
        is None
    )


def test_availability_outlook_boundaries_use_fixed_risk_buffer() -> None:
    available = [
        valuation(player_id=index, name=f"Player {index}", overall_vor=Decimal(100 - index))
        for index in range(1, 8)
    ]
    next_pick = NextUserPickContext(
        next_overall_pick=24,
        next_round=2,
        next_pick_in_round=12,
        draft_position=1,
        picks_until=4,
        is_user_on_clock=False,
        is_consecutive_turn=True,
        turn_pick_number=1,
        consecutive_pick_numbers=(1, 2),
        consecutive_pick_overalls=(24, 25),
    )

    outlooks = availability_outlooks(
        available=available,
        next_user_pick=next_pick,
        limit=7,
    )

    assert outlooks[3].available_rank == next_pick.picks_until
    assert outlooks[3].outlook == "UNLIKELY_TO_RETURN"
    assert outlooks[5].available_rank == next_pick.picks_until + AVAILABILITY_RISK_BUFFER
    assert outlooks[5].outlook == "AT_RISK"
    assert outlooks[6].available_rank == next_pick.picks_until + AVAILABILITY_RISK_BUFFER + 1
    assert outlooks[6].outlook == "COULD_RETURN"


def test_value_drop_threshold_and_true_available_rank() -> None:
    exact_drop = next_meaningful_value_drop(
        [
            valuation(player_id=1, name="Rank One", overall_vor=Decimal("100.00")),
            valuation(player_id=2, name="No VOR", overall_vor=None),
            valuation(player_id=3, name="Rank Three", overall_vor=Decimal("90.00")),
        ]
    )
    assert exact_drop is not None
    assert exact_drop.gap == MEANINGFUL_VALUE_DROP
    assert exact_drop.drop_after_available_rank == 1

    below_threshold = next_meaningful_value_drop(
        [
            valuation(player_id=1, name="Top", overall_vor=Decimal("100.00")),
            valuation(player_id=2, name="Close", overall_vor=Decimal("90.01")),
        ]
    )
    assert below_threshold is None


def test_positional_scarcity_thresholds_are_deterministic() -> None:
    next_pick = NextUserPickContext(
        next_overall_pick=6,
        next_round=1,
        next_pick_in_round=6,
        draft_position=6,
        picks_until=5,
        is_user_on_clock=False,
        is_consecutive_turn=False,
        turn_pick_number=1,
        consecutive_pick_numbers=(1,),
        consecutive_pick_overalls=(6,),
    )
    available = [
        valuation(1, "PG Top", "PG", Decimal("30.00"), 1),
        valuation(2, "SG Top", "SG", Decimal("30.00"), 1),
        valuation(3, "SF Top", "SF", Decimal("30.00"), 1),
        valuation(4, "Filler One", None, None),
        valuation(5, "Filler Two", None, None),
        valuation(6, "PG Cutoff", "PG", Decimal("20.00"), 2),
        valuation(7, "PG Depth", "PG", Decimal("1.00"), 3),
        valuation(8, "SG Cutoff", "SG", Decimal("25.00"), 2),
        valuation(9, "SG Depth", "SG", Decimal("1.00"), 3),
        valuation(10, "SF Cutoff", "SF", Decimal("26.00"), 2),
        valuation(11, "SF Depth", "SF", Decimal("1.00"), 3),
    ]

    scarcity = {
        item.position: item
        for item in positional_scarcity(available=available, next_user_pick=next_pick)
    }

    assert scarcity["PG"].projected_vor_drop == Decimal("10.00")
    assert scarcity["PG"].severity == "HIGH"
    assert scarcity["SG"].projected_vor_drop == Decimal("5.00")
    assert scarcity["SG"].severity == "MEDIUM"
    assert scarcity["SF"].projected_vor_drop == Decimal("4.00")
    assert scarcity["SF"].severity == "LOW"


@pytest.mark.asyncio
async def test_assistant_includes_next_pick_context_and_availability_outlook(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)

    for _ in range(19):
        assistant = (await client.get("/draft/assistant")).json()
        pick_response = await client.post(
            "/draft/picks",
            json={"player_id": assistant["best_available"][0]["player_id"]},
        )
        assert pick_response.status_code == 200

    response = await client.get("/draft/assistant")

    assert response.status_code == 200
    intelligence = response.json()["intelligence"]
    next_pick = intelligence["next_user_pick"]
    assert next_pick == {
        "next_overall_pick": 24,
        "next_round": 2,
        "next_pick_in_round": 12,
        "draft_position": 1,
        "picks_until": 4,
        "is_user_on_clock": False,
        "is_consecutive_turn": True,
        "turn_pick_number": 1,
        "consecutive_pick_numbers": [1, 2],
        "consecutive_pick_overalls": [24, 25],
    }
    outlooks = intelligence["availability_outlook"]
    assert len(outlooks) == 5
    assert [item["available_rank"] for item in outlooks] == [1, 2, 3, 4, 5]
    assert [item["outlook"] for item in outlooks[:4]] == [
        "UNLIKELY_TO_RETURN",
        "UNLIKELY_TO_RETURN",
        "UNLIKELY_TO_RETURN",
        "UNLIKELY_TO_RETURN",
    ]
    assert outlooks[4]["outlook"] == "AT_RISK"
    assert AVAILABILITY_RISK_BUFFER == 2


@pytest.mark.asyncio
async def test_assistant_reports_positional_scarcity_and_value_drop(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=6)

    response = await client.get("/draft/assistant", params={"limit_per_section": 10})

    assert response.status_code == 200
    intelligence = response.json()["intelligence"]
    scarcity = intelligence["positional_scarcity"]
    assert {item["position"] for item in scarcity} == {"PG", "SG", "SF", "PF", "C"}
    assert all(item["severity"] in {"HIGH", "MEDIUM", "LOW"} for item in scarcity)
    assert all(item["reasons"] for item in scarcity)
    assert any(item["projected_vor_drop"] is not None for item in scarcity)

    value_drop = intelligence["value_drop"]
    assert value_drop is not None
    assert value_drop["scan_limit"] == VALUE_DROP_SCAN_LIMIT
    assert Decimal(value_drop["meaningful_value_drop"]) == MEANINGFUL_VALUE_DROP
    assert Decimal(value_drop["gap"]) >= MEANINGFUL_VALUE_DROP
    assert value_drop["reasons"][0]["code"] == "LARGE_VALUE_DROP"


def valuation(
    player_id: int,
    name: str,
    position: str | None = "PG",
    overall_vor: Decimal | None = Decimal("1.00"),
    position_rank: int = 1,
) -> PlayerValuationRead:
    position_values = []
    if position is not None and overall_vor is not None:
        position_values.append(
            PositionValueRead(
                position=position,
                replacement_player_id=999,
                replacement_player_name="Replacement",
                replacement_fantasy_points=Decimal("0.00"),
                vor=overall_vor,
                position_rank=position_rank,
            )
        )
    return PlayerValuationRead(
        player_id=player_id,
        player_name=name,
        team="TST",
        primary_position=position,
        eligible_positions=[position] if position else [],
        compatible_roster_slots=[],
        projected_games=Decimal("1.00"),
        fantasy_points_per_game=Decimal("1.00"),
        projected_fantasy_points=Decimal("1.00"),
        position_values=position_values,
        overall_vor=overall_vor,
        best_value_position=position if position and overall_vor is not None else None,
        overall_rank=player_id if overall_vor is not None else None,
    )
