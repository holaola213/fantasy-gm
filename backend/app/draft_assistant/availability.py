from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.drafts.order import NextUserPickContext
from app.valuations.schemas import PlayerValuationRead

AVAILABILITY_RISK_BUFFER = 2


@dataclass(frozen=True)
class AvailabilityOutlook:
    player: PlayerValuationRead
    available_rank: int
    outlook: str
    reason_codes: tuple[str, ...]


def availability_outlooks(
    *,
    available: list[PlayerValuationRead],
    next_user_pick: NextUserPickContext | None,
    limit: int,
) -> list[AvailabilityOutlook]:
    ranked = [(index, item) for index, item in enumerate(available, start=1)]
    if next_user_pick is None:
        return [
            AvailabilityOutlook(
                player=item,
                available_rank=available_rank,
                outlook="COULD_RETURN",
                reason_codes=("NO_FUTURE_USER_PICK",),
            )
            for available_rank, item in ranked[:limit]
        ]

    if next_user_pick.picks_until == 0:
        return [
            AvailabilityOutlook(
                player=item,
                available_rank=available_rank,
                outlook="COULD_RETURN",
                reason_codes=("USER_ON_CLOCK",),
            )
            for available_rank, item in ranked[:limit]
        ]

    at_risk_cutoff = next_user_pick.picks_until + AVAILABILITY_RISK_BUFFER
    outlooks: list[AvailabilityOutlook] = []
    for available_rank, item in ranked[:limit]:
        if available_rank <= next_user_pick.picks_until:
            outlook = "UNLIKELY_TO_RETURN"
            reason_codes = ("INSIDE_NEXT_PICK_WINDOW",)
        elif available_rank <= at_risk_cutoff:
            outlook = "AT_RISK"
            reason_codes = ("NEAR_NEXT_PICK_WINDOW",)
        else:
            outlook = "COULD_RETURN"
            reason_codes = ("BEYOND_NEXT_PICK_WINDOW",)
        outlooks.append(
            AvailabilityOutlook(
                player=item,
                available_rank=available_rank,
                outlook=outlook,
                reason_codes=reason_codes,
            )
        )
    return outlooks


def decimal_or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")
