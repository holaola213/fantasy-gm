from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.drafts.compatibility import BASE_POSITION_KEYS, SLOT_TO_POSITIONS

BASE_POSITION_ORDER = ["PG", "SG", "SF", "PF", "C"]
ACTIVE_SLOT_KEYS = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}
DRAFTED_TARGET_SLOT_KEYS = ACTIVE_SLOT_KEYS | {"BE"}
WEIGHT_SCALE = Decimal("1000000000")


@dataclass(frozen=True)
class ValuationCandidate:
    player_id: int
    player_name: str
    projected_fantasy_points: Decimal
    fantasy_points_per_game: Decimal
    eligible_positions: tuple[str, ...]

    @property
    def normalized_name(self) -> str:
        return self.player_name.casefold()


@dataclass(frozen=True)
class ReplacementLevel:
    position: str
    demand: int
    replacement_player_id: int
    replacement_player_name: str
    replacement_fantasy_points: Decimal


class UnsupportedRosterSlotError(Exception):
    pass


class InsufficientEligiblePlayerPoolError(Exception):
    pass


class _Edge:
    def __init__(self, to: int, reverse: int, capacity: int, cost: int) -> None:
        self.to = to
        self.reverse = reverse
        self.capacity = capacity
        self.cost = cost


class _MinCostFlow:
    def __init__(self, node_count: int) -> None:
        self.graph: list[list[_Edge]] = [[] for _ in range(node_count)]

    def add_edge(self, from_node: int, to_node: int, capacity: int, cost: int) -> None:
        forward = _Edge(to_node, len(self.graph[to_node]), capacity, cost)
        reverse = _Edge(from_node, len(self.graph[from_node]), 0, -cost)
        self.graph[from_node].append(forward)
        self.graph[to_node].append(reverse)

    def flow(self, source: int, sink: int, max_flow: int) -> int:
        sent = 0
        node_count = len(self.graph)
        while sent < max_flow:
            distance = [None] * node_count
            previous_node = [-1] * node_count
            previous_edge = [-1] * node_count
            in_queue = [False] * node_count
            distance[source] = 0
            queue = [source]
            in_queue[source] = True
            for node in queue:
                in_queue[node] = False
                for edge_index, edge in enumerate(self.graph[node]):
                    if edge.capacity <= 0:
                        continue
                    next_distance = distance[node] + edge.cost
                    if distance[edge.to] is None or next_distance < distance[edge.to]:
                        distance[edge.to] = next_distance
                        previous_node[edge.to] = node
                        previous_edge[edge.to] = edge_index
                        if not in_queue[edge.to]:
                            queue.append(edge.to)
                            in_queue[edge.to] = True

            if distance[sink] is None:
                break

            add = max_flow - sent
            node = sink
            while node != source:
                edge = self.graph[previous_node[node]][previous_edge[node]]
                add = min(add, edge.capacity)
                node = previous_node[node]
            node = sink
            while node != source:
                edge = self.graph[previous_node[node]][previous_edge[node]]
                edge.capacity -= add
                self.graph[node][edge.reverse].capacity += add
                node = previous_node[node]
            sent += add
        return sent


def active_slot_demand(roster_slot_counts: dict[str, int], team_count: int) -> dict[str, int]:
    demand: dict[str, int] = {}
    for slot_key, count in roster_slot_counts.items():
        key = slot_key.strip().upper()
        if key == "IR" or count == 0:
            continue
        if key not in DRAFTED_TARGET_SLOT_KEYS:
            raise UnsupportedRosterSlotError
        if key in ACTIVE_SLOT_KEYS:
            demand[key] = demand.get(key, 0) + (count * team_count)
    return demand


def drafted_player_target(roster_slot_counts: dict[str, int], team_count: int) -> int:
    target = 0
    for slot_key, count in roster_slot_counts.items():
        key = slot_key.strip().upper()
        if key == "IR" or count == 0:
            continue
        if key not in DRAFTED_TARGET_SLOT_KEYS:
            raise UnsupportedRosterSlotError
        target += count * team_count
    return target


def calculate_replacement_levels(
    *,
    candidates: list[ValuationCandidate],
    roster_slot_counts: dict[str, int],
    team_count: int,
) -> tuple[dict[str, ReplacementLevel], dict[str, int], int, set[int]]:
    ordered_candidates = _sort_candidates(candidates)
    slot_demand = active_slot_demand(roster_slot_counts, team_count)
    total_active_demand = sum(slot_demand.values())
    if total_active_demand <= 0:
        raise InsufficientEligiblePlayerPoolError

    assigned_player_ids = _optimized_active_assignments(
        ordered_candidates=ordered_candidates,
        slot_demand=slot_demand,
    )
    if len(assigned_player_ids) < total_active_demand:
        raise InsufficientEligiblePlayerPoolError

    levels: dict[str, ReplacementLevel] = {}
    for position in BASE_POSITION_ORDER:
        replacement = next(
            (
                candidate for candidate in ordered_candidates
                if position in candidate.eligible_positions
                and candidate.player_id not in assigned_player_ids
            ),
            None,
        )
        if replacement is None:
            raise InsufficientEligiblePlayerPoolError
        levels[position] = ReplacementLevel(
            position=position,
            demand=sum(
                count
                for slot_key, count in slot_demand.items()
                if position in SLOT_TO_POSITIONS[slot_key]
            ),
            replacement_player_id=replacement.player_id,
            replacement_player_name=replacement.player_name,
            replacement_fantasy_points=replacement.projected_fantasy_points,
        )

    return (
        levels,
        slot_demand,
        drafted_player_target(roster_slot_counts, team_count),
        assigned_player_ids,
    )


def _optimized_active_assignments(
    *,
    ordered_candidates: list[ValuationCandidate],
    slot_demand: dict[str, int],
) -> set[int]:
    slots = [
        slot_key
        for slot_key in sorted(slot_demand, key=_slot_order)
        for _ in range(slot_demand[slot_key])
    ]
    source = 0
    player_offset = 1
    slot_offset = player_offset + len(ordered_candidates)
    sink = slot_offset + len(slots)
    flow = _MinCostFlow(sink + 1)

    if not ordered_candidates:
        return set()

    for player_index, candidate in enumerate(ordered_candidates):
        player_node = player_offset + player_index
        flow.add_edge(source, player_node, 1, 0)
        compatible_slots = [
            (slot_index, slot_key)
            for slot_index, slot_key in enumerate(slots)
            if set(candidate.eligible_positions) & SLOT_TO_POSITIONS[slot_key]
        ]
        weight = _weight(candidate.projected_fantasy_points)
        for slot_index, _ in compatible_slots:
            flow.add_edge(player_node, slot_offset + slot_index, 1, -weight)

    for slot_index, _ in enumerate(slots):
        flow.add_edge(slot_offset + slot_index, sink, 1, 0)

    sent = flow.flow(source, sink, len(slots))
    if sent < len(slots):
        return set()

    assigned: set[int] = set()
    for player_index, candidate in enumerate(ordered_candidates):
        player_node = player_offset + player_index
        for edge in flow.graph[player_node]:
            if slot_offset <= edge.to < sink and edge.capacity == 0:
                assigned.add(candidate.player_id)
                break
    return assigned


def _sort_candidates(candidates: list[ValuationCandidate]) -> list[ValuationCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.projected_fantasy_points,
            -candidate.fantasy_points_per_game,
            candidate.normalized_name,
            candidate.player_id,
        ),
    )


def _slot_order(slot_key: str) -> tuple[int, str]:
    order = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    return (order.index(slot_key), slot_key)


def _weight(value: Decimal) -> int:
    return int((value * WEIGHT_SCALE).to_integral_value(rounding=ROUND_HALF_UP))
