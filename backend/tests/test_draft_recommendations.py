from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.draft_assistant.availability import AvailabilityOutlook
from app.draft_assistant.recommendations import (
    RECOMMENDATION_RETURN_LIMIT,
    RecommendationInput,
    recommend_players,
    value_proximity_score,
)
from app.draft_assistant.roster_assignment import RosterPlayer, assign_roster
from app.draft_assistant.scarcity import PositionScarcity
from app.draft_assistant.value_gaps import ValueDrop
from app.valuations.schemas import PlayerValuationRead, PositionValueRead
from tests.test_draft_assistant import (
    client,
    create_started_draft,
    seed_standard_fixtures,
)


def test_value_proximity_score_uses_decimal_boundaries() -> None:
    assert value_proximity_score(
        best_vor=Decimal("100.00"),
        candidate_vor=Decimal("100.00"),
    ) == Decimal("100.00")
    assert value_proximity_score(
        best_vor=Decimal("100.00"),
        candidate_vor=Decimal("99.90"),
    ) == Decimal("99.80")
    assert value_proximity_score(
        best_vor=Decimal("100.00"),
        candidate_vor=Decimal("90.10"),
    ) == Decimal("80.20")
    assert value_proximity_score(
        best_vor=Decimal("100.00"),
        candidate_vor=Decimal("90.00"),
    ) == Decimal("80.00")
    assert value_proximity_score(
        best_vor=Decimal("100.00"),
        candidate_vor=Decimal("99.9975"),
    ) == Decimal("100.00")


def test_recommendations_keep_close_value_candidates_above_fallbacks() -> None:
    available = [
        valuation(1, "Top Guard", "PG", Decimal("100.00")),
        valuation(2, "Close Center", "C", Decimal("95.00")),
        valuation(3, "Fallback One", "SG", Decimal("89.99")),
        valuation(4, "Fallback Two", "SF", Decimal("80.00")),
        valuation(5, "Fallback Three", "PF", Decimal("79.00")),
        valuation(6, "Fallback Four", "G", Decimal("78.00"), ["PG", "SG"]),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            roster_slot_counts={"PG": 1, "C": 1, "BE": 4},
        )
    )

    assert len(recommendations) == RECOMMENDATION_RETURN_LIMIT
    assert [item.recommendation_context for item in recommendations[:2]] == [
        "CLOSE_VALUE",
        "CLOSE_VALUE",
    ]
    assert [item.player_id for item in recommendations[2:]] == [3, 4, 5]
    assert all(item.score_breakdown is not None for item in recommendations[:2])
    assert all(item.score_breakdown is None for item in recommendations[2:])


def test_fallback_candidates_are_limited_to_raw_top_ten_available_players() -> None:
    available = [
        valuation(1, "Top Guard", "PG", Decimal("100.00")),
        *[
            valuation(index, f"Ineligible {index}", None, Decimal("95.00"))
            for index in range(2, 11)
        ],
        valuation(11, "Outside Raw Top Ten", "C", Decimal("89.99")),
    ]

    recommendations = recommend_players(recommendation_input(available=available))

    assert [item.player_id for item in recommendations] == [1]
    assert all(
        item.recommendation_context == "CLOSE_VALUE" for item in recommendations
    )


def test_fallback_candidates_preserve_original_available_order() -> None:
    available = [
        valuation(1, "Top Guard", "PG", Decimal("100.00")),
        valuation(2, "Fallback Bench", "PG", Decimal("89.99")),
        valuation(3, "Fallback Starter Fit", "C", Decimal("80.00")),
        valuation(4, "Fallback Flex", "SG", Decimal("70.00")),
    ]
    current = [
        roster_player(101, "Current Guard", ("PG",), Decimal("200.00"), 1),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            current_roster=current,
            roster_slot_counts={"PG": 1, "C": 1, "BE": 4},
        )
    )

    assert [item.player_id for item in recommendations] == [1, 2, 3, 4]
    assert [item.recommendation_context for item in recommendations[1:]] == [
        "FALLBACK_VALUE",
        "FALLBACK_VALUE",
        "FALLBACK_VALUE",
    ]


def test_fewer_than_five_available_players_returns_only_available_recommendations() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[
                valuation(1, "Top Guard", "PG", Decimal("100.00")),
                valuation(2, "Close Wing", "SF", Decimal("99.00")),
            ]
        )
    )

    assert [item.player_id for item in recommendations] == [1, 2]


def test_deterministic_tie_ordering_uses_existing_rank_and_identity() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[
                valuation(
                    2,
                    "Beta Tie",
                    "PG",
                    Decimal("100.00"),
                    projected_fantasy_points=Decimal("500.00"),
                    overall_rank=2,
                ),
                valuation(
                    1,
                    "Alpha Tie",
                    "PG",
                    Decimal("100.00"),
                    projected_fantasy_points=Decimal("500.00"),
                    overall_rank=1,
                ),
            ],
            roster_slot_counts={"PG": 2, "BE": 0},
        )
    )

    assert [item.player_id for item in recommendations] == [1, 2]


def test_roster_fit_reorders_only_close_value_candidates() -> None:
    available = [
        valuation(1, "Bench Value", "PF", Decimal("100.00")),
        valuation(2, "Open Center", "C", Decimal("99.00")),
        valuation(3, "Flex Guard", "SG", Decimal("98.50")),
    ]
    current = [
        roster_player(101, "Current Point", ("PG",), Decimal("300.00"), 1),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            current_roster=current,
            roster_slot_counts={"PG": 1, "C": 1, "G": 1, "BE": 4},
        )
    )

    assert recommendations[0].player_id == 2
    assert recommendations[0].projected_roster_assignment.assignment_type == "active"
    assert recommendations[0].projected_roster_assignment.assigned_slot == "C"
    assert recommendations[0].score_breakdown is not None
    assert recommendations[0].score_breakdown.roster_fit_score == Decimal("7.00")


def test_single_position_player_does_not_receive_multi_position_flexibility() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[valuation(1, "Point Only", "PG", Decimal("100.00"))],
            roster_slot_counts={"PG": 1, "G": 1, "BE": 0},
        )
    )

    reason_codes = {reason.code for reason in recommendations[0].reasons}
    assert "MULTI_POSITION_FLEXIBILITY" not in reason_codes


def test_multi_position_flexibility_requires_multiple_active_paths() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[
                valuation(
                    1,
                    "Guard Flex",
                    "PG",
                    Decimal("100.00"),
                    eligible_positions=["PG", "SG"],
                )
            ],
            roster_slot_counts={"PG": 1, "SG": 1, "G": 1, "BE": 0},
        )
    )

    reason_codes = {reason.code for reason in recommendations[0].reasons}
    assert "MULTI_POSITION_FLEXIBILITY" in reason_codes


def test_bench_only_candidate_gets_warning() -> None:
    current = [
        roster_player(101, "Current Point", ("PG",), Decimal("900.00"), 1),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=[valuation(1, "Bench Point", "PG", Decimal("100.00"))],
            current_roster=current,
            roster_slot_counts={"PG": 1, "BE": 1},
        )
    )

    assert recommendations[0].projected_roster_assignment.assignment_type == "bench"
    assert {warning.code for warning in recommendations[0].warnings} == {"BENCH_ONLY_FIT"}


def test_unassigned_candidate_gets_missing_context_warning() -> None:
    current = [
        roster_player(101, "Current Point", ("PG",), Decimal("900.00"), 1),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=[valuation(1, "Unassigned Point", "PG", Decimal("100.00"))],
            current_roster=current,
            roster_slot_counts={"PG": 1, "BE": 0},
        )
    )

    assert recommendations[0].projected_roster_assignment.assignment_type == "unassigned"
    assert "MISSING_CONTEXT" in {
        warning.code for warning in recommendations[0].warnings
    }


def test_availability_scoring_is_disabled_when_user_is_on_clock() -> None:
    available = [valuation(1, "Top Guard", "PG", Decimal("100.00"))]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            availability={
                1: AvailabilityOutlook(
                    player=available[0],
                    available_rank=1,
                    outlook="UNLIKELY_TO_RETURN",
                    reason_codes=("INSIDE_NEXT_PICK_WINDOW",),
                )
            },
            is_user_on_clock=True,
        )
    )

    assert recommendations[0].score_breakdown is not None
    assert recommendations[0].score_breakdown.availability_score == Decimal("0.00")
    assert "UNLIKELY_TO_RETURN" not in {
        reason.code for reason in recommendations[0].reasons
    }


def test_no_future_user_pick_does_not_add_return_warning() -> None:
    available = [valuation(1, "Final Pick", "PG", Decimal("100.00"))]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            availability={
                1: AvailabilityOutlook(
                    player=available[0],
                    available_rank=1,
                    outlook="COULD_RETURN",
                    reason_codes=("NO_FUTURE_USER_PICK",),
                )
            },
        )
    )

    assert recommendations[0].score_breakdown is not None
    assert recommendations[0].score_breakdown.availability_score == Decimal("0.00")
    assert "COULD_RETURN_LATER" not in {
        warning.code for warning in recommendations[0].warnings
    }


def test_availability_scorer_uses_outlook_boundaries() -> None:
    available = [
        valuation(1, "Unlikely", "PG", Decimal("100.00")),
        valuation(2, "At Risk", "SG", Decimal("99.00")),
        valuation(3, "Could Return", "SF", Decimal("98.00")),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            availability={
                1: availability(available[0], "UNLIKELY_TO_RETURN"),
                2: availability(available[1], "AT_RISK"),
                3: availability(available[2], "COULD_RETURN"),
            },
        )
    )

    breakdowns = {
        item.player_id: item.score_breakdown for item in recommendations
    }
    assert breakdowns[1] is not None
    assert breakdowns[1].availability_score == Decimal("3.00")
    assert breakdowns[2] is not None
    assert breakdowns[2].availability_score == Decimal("1.50")
    assert breakdowns[3] is not None
    assert breakdowns[3].availability_score == Decimal("0.00")


def test_scarcity_scores_high_medium_and_low_thresholds() -> None:
    available = [
        valuation(1, "High Scarcity", "PG", Decimal("100.00")),
        valuation(2, "Medium Scarcity", "SG", Decimal("99.00")),
        valuation(3, "Low Scarcity", "SF", Decimal("98.00")),
    ]

    recommendations = recommend_players(
        recommendation_input(
            available=available,
            scarcity={
                "PG": scarcity("PG", "HIGH", available[0]),
                "SG": scarcity("SG", "MEDIUM", available[1]),
                "SF": scarcity("SF", "LOW", available[2]),
            },
        )
    )

    breakdowns = {
        item.player_id: item.score_breakdown for item in recommendations
    }
    assert breakdowns[1] is not None
    assert breakdowns[1].scarcity_score == Decimal("3.00")
    assert breakdowns[2] is not None
    assert breakdowns[2].scarcity_score == Decimal("1.50")
    assert breakdowns[3] is not None
    assert breakdowns[3].scarcity_score == Decimal("0.00")


def test_value_drop_bonus_uses_true_available_rank() -> None:
    available = [
        valuation(1, "Top", "PG", Decimal("100.00")),
        valuation(2, "Skipped Missing VOR", "SG", None),
        valuation(3, "Before Drop", "C", Decimal("95.00")),
        valuation(4, "After Drop", "SF", Decimal("84.99")),
    ]
    drop = ValueDrop(
        scan_limit=25,
        drop_after_available_rank=3,
        before_player=available[2],
        after_player=available[3],
        gap=Decimal("10.01"),
        reason_codes=("LARGE_VALUE_DROP",),
    )

    recommendations = recommend_players(
        recommendation_input(available=available, value_drop=drop)
    )

    before_drop = next(item for item in recommendations if item.player_id == 3)
    assert before_drop.score_breakdown is not None
    assert before_drop.score_breakdown.value_drop_score == Decimal("1.50")


def test_value_drop_threshold_reason_at_exactly_ten_only_for_close_candidates() -> None:
    available = [
        valuation(1, "Top", "PG", Decimal("100.00")),
        valuation(2, "Exact Window", "SG", Decimal("90.00")),
        valuation(3, "Below Window", "SF", Decimal("89.99")),
    ]
    drop = ValueDrop(
        scan_limit=25,
        drop_after_available_rank=2,
        before_player=available[1],
        after_player=available[2],
        gap=Decimal("0.01"),
        reason_codes=("LARGE_VALUE_DROP",),
    )

    recommendations = recommend_players(
        recommendation_input(available=available, value_drop=drop)
    )

    exact_window = next(item for item in recommendations if item.player_id == 2)
    below_window = next(item for item in recommendations if item.player_id == 3)
    assert exact_window.recommendation_context == "CLOSE_VALUE"
    assert exact_window.score_breakdown is not None
    assert exact_window.score_breakdown.value_proximity_score == Decimal("80.00")
    assert below_window.recommendation_context == "FALLBACK_VALUE"
    assert below_window.score_breakdown is None


def test_significant_reach_warning_uses_exact_twenty_point_boundary() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[
                valuation(1, "Top", "PG", Decimal("100.00")),
                valuation(2, "Exact Reach", "SG", Decimal("80.00")),
                valuation(3, "Below Reach", "SF", Decimal("80.01")),
            ]
        )
    )

    warnings_by_player_id = {
        item.player_id: {warning.code for warning in item.warnings}
        for item in recommendations
    }
    assert "SIGNIFICANT_VALUE_REACH" in warnings_by_player_id[2]
    assert "SIGNIFICANT_VALUE_REACH" not in warnings_by_player_id[3]


def test_players_without_vor_or_eligibility_are_not_recommendation_eligible() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[
                valuation(1, "No VOR", "PG", None),
                valuation(2, "No Eligibility", None, Decimal("100.00")),
                valuation(3, "Eligible", "C", Decimal("90.00")),
            ]
        )
    )

    assert [item.player_id for item in recommendations] == [3]


def test_recommendation_explanations_avoid_absolute_language() -> None:
    recommendations = recommend_players(
        recommendation_input(
            available=[
                valuation(1, "Top", "PG", Decimal("100.00")),
                valuation(2, "Risk", "SG", Decimal("99.00")),
            ],
            availability={
                1: availability(
                    valuation(1, "Top", "PG", Decimal("100.00")),
                    "UNLIKELY_TO_RETURN",
                ),
                2: availability(
                    valuation(2, "Risk", "SG", Decimal("99.00")),
                    "AT_RISK",
                ),
            },
        )
    )

    absolute_words = [
        "guaranteed",
        "must draft",
        "certain",
        "safe",
        "definitely",
        "will not return",
    ]
    for item in recommendations:
        lowered = item.explanation.casefold()
        assert not any(word in lowered for word in absolute_words)


@pytest.mark.asyncio
async def test_assistant_response_includes_recommendations_and_uses_one_valuation_pass(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.draft_assistant import service as assistant_service

    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)

    calls = 0
    original = assistant_service.ValuationService.list_valuations

    async def counting_list_valuations(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(
        assistant_service.ValuationService,
        "list_valuations",
        counting_list_valuations,
    )

    response = await client.get("/draft/assistant")

    assert response.status_code == 200
    body = response.json()
    assert calls == 1
    assert 0 < len(body["recommendations"]) <= RECOMMENDATION_RETURN_LIMIT
    assert "best_available" in body
    assert "intelligence" in body
    assert "roster_summary" in body
    assert body["recommendations"][0]["score_breakdown"] is not None
    contexts = [item["recommendation_context"] for item in body["recommendations"]]
    if "FALLBACK_VALUE" in contexts:
        first_fallback = contexts.index("FALLBACK_VALUE")
        assert contexts[first_fallback:] == ["FALLBACK_VALUE"] * (
            len(contexts) - first_fallback
        )
        assert all(
            item["score_breakdown"] is None
            for item in body["recommendations"][first_fallback:]
        )


@pytest.mark.asyncio
async def test_pick_undo_and_reset_recompute_recommendations(
    client: AsyncClient,
) -> None:
    await seed_standard_fixtures(client)
    await create_started_draft(client, user_position=1)

    before = (await client.get("/draft/assistant")).json()
    recommended_player_id = before["recommendations"][0]["player_id"]

    pick_response = await client.post(
        "/draft/picks",
        json={"player_id": recommended_player_id},
    )
    assert pick_response.status_code == 200
    after_pick = (await client.get("/draft/assistant")).json()
    assert all(
        item["player_id"] != recommended_player_id
        for item in after_pick["recommendations"]
    )

    undo_response = await client.delete("/draft/picks/latest")
    assert undo_response.status_code == 200
    after_undo = (await client.get("/draft/assistant")).json()
    assert after_undo["recommendations"][0]["player_id"] == recommended_player_id

    reset_response = await client.post("/draft/reset")
    assert reset_response.status_code == 200
    unavailable = await client.get("/draft/assistant")
    assert unavailable.status_code == 409
    assert unavailable.json() == {"detail": "active draft required"}


def recommendation_input(
    *,
    available: list[PlayerValuationRead],
    current_roster: list[RosterPlayer] | None = None,
    roster_slot_counts: dict[str, int] | None = None,
    availability: dict[int, AvailabilityOutlook] | None = None,
    scarcity: dict[str, PositionScarcity] | None = None,
    value_drop: ValueDrop | None = None,
    is_user_on_clock: bool = False,
) -> RecommendationInput:
    roster_slot_counts = roster_slot_counts or {
        "PG": 1,
        "SG": 1,
        "SF": 1,
        "PF": 1,
        "C": 1,
        "G": 1,
        "F": 1,
        "UTIL": 1,
        "BE": 4,
    }
    current_roster = current_roster or []
    current_assignment = assign_roster(
        players=current_roster,
        roster_slot_counts=roster_slot_counts,
    )
    return RecommendationInput(
        available=available,
        current_roster_players=current_roster,
        current_assignment=current_assignment,
        roster_slot_counts=roster_slot_counts,
        availability_by_player_id=availability or {},
        scarcity_by_position=scarcity or {},
        value_drop=value_drop,
        is_user_on_clock=is_user_on_clock,
    )


def valuation(
    player_id: int,
    name: str,
    position: str | None,
    overall_vor: Decimal | None,
    eligible_positions: list[str] | None = None,
    projected_fantasy_points: Decimal | None = None,
    overall_rank: int | None = None,
) -> PlayerValuationRead:
    eligible_positions = eligible_positions or ([position] if position else [])
    position_values = [
        PositionValueRead(
            position=eligible_position,
            replacement_player_id=999,
            replacement_player_name="Replacement",
            replacement_fantasy_points=Decimal("0.00"),
            vor=overall_vor,
            position_rank=player_id,
        )
        for eligible_position in eligible_positions
        if overall_vor is not None
    ]
    return PlayerValuationRead(
        player_id=player_id,
        player_name=name,
        team="TST",
        primary_position=position,
        eligible_positions=eligible_positions,
        compatible_roster_slots=[],
        projected_games=Decimal("82.00"),
        fantasy_points_per_game=Decimal("10.00"),
        projected_fantasy_points=(
            projected_fantasy_points
            if projected_fantasy_points is not None
            else Decimal("820.00") - Decimal(player_id)
        ),
        position_values=position_values,
        overall_vor=overall_vor,
        best_value_position=eligible_positions[0] if position_values else None,
        overall_rank=(
            overall_rank
            if overall_rank is not None
            else player_id
            if overall_vor is not None
            else None
        ),
    )


def roster_player(
    player_id: int,
    name: str,
    eligible_positions: tuple[str, ...],
    projected_fantasy_points: Decimal,
    overall_pick: int,
) -> RosterPlayer:
    return RosterPlayer(
        draft_pick_id=player_id,
        player_id=player_id,
        player_name=name,
        eligible_positions=eligible_positions,
        projected_fantasy_points=projected_fantasy_points,
        overall_pick=overall_pick,
    )


def availability(
    player: PlayerValuationRead,
    outlook: str,
) -> AvailabilityOutlook:
    reason_code = {
        "UNLIKELY_TO_RETURN": "INSIDE_NEXT_PICK_WINDOW",
        "AT_RISK": "NEAR_NEXT_PICK_WINDOW",
        "COULD_RETURN": "BEYOND_NEXT_PICK_WINDOW",
    }[outlook]
    return AvailabilityOutlook(
        player=player,
        available_rank=player.player_id,
        outlook=outlook,
        reason_codes=(reason_code,),
    )


def scarcity(
    position: str,
    severity: str,
    player: PlayerValuationRead,
) -> PositionScarcity:
    value = player.position_values[0]
    drop = {
        "HIGH": Decimal("10.00"),
        "MEDIUM": Decimal("5.00"),
        "LOW": Decimal("4.99"),
    }[severity]
    return PositionScarcity(
        position=position,
        top_player=player,
        top_position_value=value,
        cutoff_player=player,
        cutoff_position_value=value,
        projected_vor_drop=drop,
        players_before_next_pick=1,
        meaningful_options_remaining=1 if severity == "HIGH" else 3,
        severity=severity,
        reason_codes=("LIMITED_POSITION_DEPTH",)
        if severity == "HIGH"
        else ("POSITION_VALUE_DROP",)
        if severity == "MEDIUM"
        else ("POSITION_DEPTH_AVAILABLE",),
    )
