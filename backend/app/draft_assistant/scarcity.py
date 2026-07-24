from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.draft_assistant.availability import decimal_or_zero
from app.drafts.compatibility import BASE_POSITION_ORDER
from app.drafts.order import NextUserPickContext
from app.valuations.schemas import PlayerValuationRead, PositionValueRead

SCARCITY_HIGH_DROP = Decimal("10.00")
SCARCITY_MEDIUM_DROP = Decimal("5.00")
SCARCITY_LOW_DEPTH = 2


@dataclass(frozen=True)
class PositionScarcity:
    position: str
    top_player: PlayerValuationRead | None
    top_position_value: PositionValueRead | None
    cutoff_player: PlayerValuationRead | None
    cutoff_position_value: PositionValueRead | None
    projected_vor_drop: Decimal | None
    players_before_next_pick: int
    meaningful_options_remaining: int
    severity: str
    reason_codes: tuple[str, ...]


def positional_scarcity(
    *,
    available: list[PlayerValuationRead],
    next_user_pick: NextUserPickContext | None,
) -> list[PositionScarcity]:
    available_rank_by_player_id = {
        item.player_id: rank for rank, item in enumerate(available, start=1)
    }
    picks_until = next_user_pick.picks_until if next_user_pick else 0
    rows = [
        _position_scarcity(
            position=position,
            available=available,
            available_rank_by_player_id=available_rank_by_player_id,
            picks_until=picks_until,
        )
        for position in BASE_POSITION_ORDER
    ]
    return sorted(rows, key=_scarcity_sort_key)


def _position_scarcity(
    *,
    position: str,
    available: list[PlayerValuationRead],
    available_rank_by_player_id: dict[int, int],
    picks_until: int,
) -> PositionScarcity:
    pairs = [
        (item, value)
        for item in available
        for value in item.position_values
        if value.position == position
    ]
    pairs.sort(
        key=lambda pair: (
            pair[1].position_rank,
            pair[0].overall_rank is None,
            pair[0].overall_rank or 999999999,
            pair[0].player_name.casefold(),
            pair[0].player_id,
        )
    )
    if not pairs:
        return PositionScarcity(
            position=position,
            top_player=None,
            top_position_value=None,
            cutoff_player=None,
            cutoff_position_value=None,
            projected_vor_drop=None,
            players_before_next_pick=0,
            meaningful_options_remaining=0,
            severity="HIGH",
            reason_codes=("LIMITED_POSITION_DEPTH",),
        )

    top_player, top_value = pairs[0]
    cutoff_pair = next(
        (
            pair
            for pair in pairs
            if available_rank_by_player_id[pair[0].player_id] > picks_until
        ),
        None,
    )
    cutoff_player, cutoff_value = cutoff_pair if cutoff_pair else (None, None)
    players_before_next_pick = sum(
        1
        for item, _ in pairs
        if available_rank_by_player_id[item.player_id] <= picks_until
    )
    meaningful_options_remaining = sum(
        1 for _, value in pairs if value.vor > Decimal("0")
    )
    drop = (
        decimal_or_zero(top_value.vor) - decimal_or_zero(cutoff_value.vor)
        if cutoff_value is not None
        else None
    )
    severity = _severity(drop, meaningful_options_remaining, cutoff_value)
    reason_codes = []
    if drop is not None and drop >= SCARCITY_MEDIUM_DROP:
        reason_codes.append("POSITION_VALUE_DROP")
    if meaningful_options_remaining <= SCARCITY_LOW_DEPTH:
        reason_codes.append("LIMITED_POSITION_DEPTH")
    if not reason_codes:
        reason_codes.append("POSITION_DEPTH_AVAILABLE")

    return PositionScarcity(
        position=position,
        top_player=top_player,
        top_position_value=top_value,
        cutoff_player=cutoff_player,
        cutoff_position_value=cutoff_value,
        projected_vor_drop=drop,
        players_before_next_pick=players_before_next_pick,
        meaningful_options_remaining=meaningful_options_remaining,
        severity=severity,
        reason_codes=tuple(reason_codes),
    )


def _severity(
    drop: Decimal | None,
    meaningful_options_remaining: int,
    cutoff_value: PositionValueRead | None,
) -> str:
    if cutoff_value is None:
        return "HIGH"
    if (
        (drop is not None and drop >= SCARCITY_HIGH_DROP)
        or meaningful_options_remaining <= SCARCITY_LOW_DEPTH
    ):
        return "HIGH"
    if drop is not None and drop >= SCARCITY_MEDIUM_DROP:
        return "MEDIUM"
    return "LOW"


def _scarcity_sort_key(item: PositionScarcity) -> tuple:
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[item.severity]
    drop = item.projected_vor_drop or Decimal("-999999")
    return (
        severity_rank,
        -drop,
        BASE_POSITION_ORDER.index(item.position),
    )
