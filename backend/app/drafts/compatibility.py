BASE_POSITION_ORDER = ("PG", "SG", "SF", "PF", "C")
BASE_POSITION_KEYS = set(BASE_POSITION_ORDER)
DRAFT_ROSTER_SLOT_KEYS = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "BE"}

SLOT_TO_POSITIONS = {
    "PG": {"PG"},
    "SG": {"SG"},
    "SF": {"SF"},
    "PF": {"PF"},
    "C": {"C"},
    "G": {"PG", "SG"},
    "F": {"SF", "PF"},
    "UTIL": {"PG", "SG", "SF", "PF", "C"},
    "BE": {"PG", "SG", "SF", "PF", "C"},
}


def normalize_position_key(value: str) -> str:
    return value.strip().upper()


def compatible_roster_slots(
    eligible_positions: list[str],
    configured_slot_keys: list[str],
) -> list[str]:
    eligible = {normalize_position_key(position) for position in eligible_positions}
    compatible = []
    for slot_key in configured_slot_keys:
        normalized_slot = normalize_position_key(slot_key)
        if normalized_slot not in DRAFT_ROSTER_SLOT_KEYS:
            continue
        if eligible & SLOT_TO_POSITIONS[normalized_slot]:
            compatible.append(normalized_slot)
    return compatible


def calculate_draft_rounds(roster_slot_counts: dict[str, int]) -> int:
    rounds = 0
    for slot_key, count in roster_slot_counts.items():
        normalized_slot = normalize_position_key(slot_key)
        if normalized_slot == "IR" or count == 0:
            continue
        if normalized_slot not in DRAFT_ROSTER_SLOT_KEYS:
            raise ValueError(f"unsupported draft roster slot key: {normalized_slot}")
        rounds += count
    if rounds <= 0:
        raise ValueError("draft must have at least one round")
    return rounds


def snake_pick_details(overall_pick: int, team_count: int) -> tuple[int, int, int]:
    round_number = ((overall_pick - 1) // team_count) + 1
    pick_in_round = ((overall_pick - 1) % team_count) + 1
    if round_number % 2 == 1:
        draft_position = pick_in_round
    else:
        draft_position = team_count - pick_in_round + 1
    return round_number, pick_in_round, draft_position
