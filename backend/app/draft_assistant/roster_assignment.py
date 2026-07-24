from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.drafts.compatibility import SLOT_TO_POSITIONS

ACTIVE_SLOT_KEYS = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}
DRAFTABLE_SLOT_KEYS = ACTIVE_SLOT_KEYS | {"BE"}
RESTRICTIVE_SLOT_KEYS = {"PG", "SG", "SF", "PF", "C"}
SLOT_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


@dataclass(frozen=True)
class SlotInstance:
    slot: str
    slot_index: int


@dataclass(frozen=True)
class RosterPlayer:
    draft_pick_id: int
    player_id: int
    player_name: str
    eligible_positions: tuple[str, ...]
    projected_fantasy_points: Decimal | None
    overall_pick: int

    @property
    def normalized_name(self) -> str:
        return self.player_name.casefold()


@dataclass(frozen=True)
class ActiveAssignment:
    player: RosterPlayer
    slot: SlotInstance


@dataclass(frozen=True)
class BenchAssignment:
    player: RosterPlayer
    bench_index: int


@dataclass(frozen=True)
class UnassignedPlayer:
    player: RosterPlayer
    reason: str


@dataclass(frozen=True)
class RosterAssignmentResult:
    active_slots: list[SlotInstance]
    bench_slots_total: int
    draftable_roster_capacity: int
    active_assignments: list[ActiveAssignment]
    bench_assignments: list[BenchAssignment]
    unfilled_slots: list[SlotInstance]
    unassigned_players: list[UnassignedPlayer]


class UnsupportedRosterSlotError(Exception):
    pass


def configured_slot_instances(
    roster_slot_counts: dict[str, int],
) -> tuple[list[SlotInstance], int, int]:
    active_slots: list[SlotInstance] = []
    bench_slots_total = 0
    draftable_capacity = 0
    for raw_slot, count in roster_slot_counts.items():
        slot = raw_slot.strip().upper()
        if slot == "IR" or count == 0:
            continue
        if slot not in DRAFTABLE_SLOT_KEYS:
            raise UnsupportedRosterSlotError
        draftable_capacity += count
        if slot == "BE":
            bench_slots_total += count
            continue
        for slot_index in range(1, count + 1):
            active_slots.append(SlotInstance(slot=slot, slot_index=slot_index))
    active_slots.sort(key=_slot_key)
    return active_slots, bench_slots_total, draftable_capacity


def assign_roster(
    *,
    players: list[RosterPlayer],
    roster_slot_counts: dict[str, int],
) -> RosterAssignmentResult:
    active_slots, bench_slots_total, draftable_capacity = configured_slot_instances(
        roster_slot_counts
    )
    assignable_players = [player for player in players if player.eligible_positions]
    unassigned = [
        UnassignedPlayer(player=player, reason="missing eligibility")
        for player in players
        if not player.eligible_positions
    ]
    active_assignments = _assign_active_slots(
        players=assignable_players,
        active_slots=active_slots,
    )
    active_player_ids = {assignment.player.player_id for assignment in active_assignments}
    unfilled_slots = [
        slot
        for slot in active_slots
        if not any(_same_slot(slot, assignment.slot) for assignment in active_assignments)
    ]
    remaining_players = [
        player
        for player in sorted(assignable_players, key=lambda item: item.overall_pick)
        if player.player_id not in active_player_ids
    ]
    bench_assignments = [
        BenchAssignment(player=player, bench_index=index)
        for index, player in enumerate(remaining_players[:bench_slots_total], start=1)
    ]
    for player in remaining_players[bench_slots_total:]:
        unassigned.append(UnassignedPlayer(player=player, reason="roster capacity exceeded"))

    active_assignments.sort(key=lambda item: _slot_key(item.slot))
    unfilled_slots.sort(key=_slot_key)
    return RosterAssignmentResult(
        active_slots=active_slots,
        bench_slots_total=bench_slots_total,
        draftable_roster_capacity=draftable_capacity,
        active_assignments=active_assignments,
        bench_assignments=bench_assignments,
        unfilled_slots=unfilled_slots,
        unassigned_players=unassigned,
    )


def matching_open_slots(
    *,
    eligible_positions: list[str],
    open_slots: list[SlotInstance],
) -> list[SlotInstance]:
    eligible = set(eligible_positions)
    matches = [
        slot for slot in open_slots if eligible & SLOT_TO_POSITIONS[slot.slot]
    ]
    return sorted(matches, key=_slot_key)


def _assign_active_slots(
    *,
    players: list[RosterPlayer],
    active_slots: list[SlotInstance],
) -> list[ActiveAssignment]:
    if not players or not active_slots:
        return []
    flexibility = {
        player.player_id: _flexibility(player, active_slots) for player in players
    }
    states: dict[int, tuple[tuple, list[ActiveAssignment]]] = {0: ((0, Decimal("0"), 0), [])}
    for slot in active_slots:
        next_states = dict(states)
        for mask, (score, assignments) in states.items():
            for index, player in enumerate(players):
                player_bit = 1 << index
                if mask & player_bit:
                    continue
                if not _compatible(player, slot):
                    continue
                projected = player.projected_fantasy_points or Decimal("0")
                preservation = _preservation_score(
                    player_flexibility=flexibility[player.player_id],
                    slot=slot,
                )
                next_score = (
                    score[0] + 1,
                    score[1] + projected,
                    score[2] + preservation,
                )
                next_assignments = [
                    *assignments,
                    ActiveAssignment(player=player, slot=slot),
                ]
                next_mask = mask | player_bit
                current = next_states.get(next_mask)
                if current is None or _state_key(next_score, next_assignments) > _state_key(
                    current[0], current[1]
                ):
                    next_states[next_mask] = (next_score, next_assignments)
        states = next_states
    _, best_assignments = max(
        states.values(),
        key=lambda state: _state_key(state[0], state[1]),
    )
    return best_assignments


def _state_key(score: tuple, assignments: list[ActiveAssignment]) -> tuple:
    return (
        score[0],
        score[1],
        score[2],
        tuple(
            (
                -SLOT_ORDER.index(assignment.slot.slot),
                -assignment.slot.slot_index,
                assignment.player.projected_fantasy_points or Decimal("0"),
                _reverse_name_key(assignment.player.normalized_name),
                -assignment.player.player_id,
            )
            for assignment in sorted(assignments, key=lambda item: _slot_key(item.slot))
        ),
    )


def _reverse_name_key(value: str) -> tuple[int, ...]:
    return tuple(-ord(char) for char in value)


def _preservation_score(*, player_flexibility: int, slot: SlotInstance) -> int:
    if slot.slot in RESTRICTIVE_SLOT_KEYS:
        return 100 - player_flexibility
    return player_flexibility


def _flexibility(player: RosterPlayer, active_slots: list[SlotInstance]) -> int:
    return len({slot.slot for slot in active_slots if _compatible(player, slot)})


def _compatible(player: RosterPlayer, slot: SlotInstance) -> bool:
    return bool(set(player.eligible_positions) & SLOT_TO_POSITIONS[slot.slot])


def _slot_key(slot: SlotInstance) -> tuple[int, int]:
    return (SLOT_ORDER.index(slot.slot), slot.slot_index)


def _same_slot(left: SlotInstance, right: SlotInstance) -> bool:
    return left.slot == right.slot and left.slot_index == right.slot_index
