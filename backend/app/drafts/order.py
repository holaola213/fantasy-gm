from __future__ import annotations

from dataclasses import dataclass

from app.drafts.compatibility import snake_pick_details


@dataclass(frozen=True)
class ScheduledPick:
    overall_pick: int
    round_number: int
    pick_in_round: int
    draft_position: int


@dataclass(frozen=True)
class NextUserPickContext:
    next_overall_pick: int
    next_round: int
    next_pick_in_round: int
    draft_position: int
    picks_until: int
    is_user_on_clock: bool
    is_consecutive_turn: bool
    turn_pick_number: int
    consecutive_pick_numbers: tuple[int, ...]
    consecutive_pick_overalls: tuple[int, ...]


def scheduled_pick(overall_pick: int, team_count: int) -> ScheduledPick:
    round_number, pick_in_round, draft_position = snake_pick_details(
        overall_pick,
        team_count,
    )
    return ScheduledPick(
        overall_pick=overall_pick,
        round_number=round_number,
        pick_in_round=pick_in_round,
        draft_position=draft_position,
    )


def next_user_pick_context(
    *,
    current_overall_pick: int,
    team_count: int,
    rounds: int,
    user_draft_position: int,
) -> NextUserPickContext | None:
    total_picks = team_count * rounds
    if current_overall_pick > total_picks:
        return None

    next_pick = None
    for overall_pick in range(current_overall_pick, total_picks + 1):
        scheduled = scheduled_pick(overall_pick, team_count)
        if scheduled.draft_position == user_draft_position:
            next_pick = scheduled
            break
    if next_pick is None:
        return None

    turn_start = next_pick.overall_pick
    candidate = next_pick.overall_pick - 1
    while candidate >= 1:
        scheduled = scheduled_pick(candidate, team_count)
        if scheduled.draft_position != user_draft_position:
            break
        turn_start = candidate
        candidate -= 1

    consecutive = []
    candidate = turn_start
    while candidate <= total_picks:
        scheduled = scheduled_pick(candidate, team_count)
        if scheduled.draft_position != user_draft_position:
            break
        consecutive.append(candidate)
        candidate += 1
    turn_pick_number = consecutive.index(next_pick.overall_pick) + 1

    picks_until = max(next_pick.overall_pick - current_overall_pick, 0)
    return NextUserPickContext(
        next_overall_pick=next_pick.overall_pick,
        next_round=next_pick.round_number,
        next_pick_in_round=next_pick.pick_in_round,
        draft_position=user_draft_position,
        picks_until=picks_until,
        is_user_on_clock=picks_until == 0,
        is_consecutive_turn=len(consecutive) > 1,
        turn_pick_number=turn_pick_number,
        consecutive_pick_numbers=tuple(
            index for index in range(1, len(consecutive) + 1)
        ),
        consecutive_pick_overalls=tuple(consecutive),
    )
