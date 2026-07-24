from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.draft_assistant.availability import decimal_or_zero
from app.valuations.schemas import PlayerValuationRead

MEANINGFUL_VALUE_DROP = Decimal("10.00")
VALUE_DROP_SCAN_LIMIT = 25


@dataclass(frozen=True)
class ValueDrop:
    scan_limit: int
    drop_after_available_rank: int
    before_player: PlayerValuationRead
    after_player: PlayerValuationRead
    gap: Decimal
    reason_codes: tuple[str, ...]


def next_meaningful_value_drop(
    available: list[PlayerValuationRead],
) -> ValueDrop | None:
    scan = [
        (available_rank, item)
        for available_rank, item in enumerate(
            available[:VALUE_DROP_SCAN_LIMIT],
            start=1,
        )
        if item.overall_vor is not None
    ]
    for index in range(len(scan) - 1):
        before_rank, before = scan[index]
        _, after = scan[index + 1]
        gap = decimal_or_zero(before.overall_vor) - decimal_or_zero(after.overall_vor)
        if gap >= MEANINGFUL_VALUE_DROP:
            return ValueDrop(
                scan_limit=VALUE_DROP_SCAN_LIMIT,
                drop_after_available_rank=before_rank,
                before_player=before,
                after_player=after,
                gap=gap,
                reason_codes=("LARGE_VALUE_DROP",),
            )
    return None
