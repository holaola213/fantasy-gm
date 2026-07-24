from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation

from app.projections.providers.models import ProjectionPlayer
from app.projections.providers.validation import ProjectionProviderValidationError


REQUIRED_COLUMNS = {
    "player_id",
    "full_name",
    "games",
    "minutes_per_game",
    "fgm",
    "fga",
    "ftm",
    "fta",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
}
OPTIONAL_COLUMNS = {
    "team",
    "primary_position",
    "positions",
    "is_active",
}
NUMERIC_FIELDS = (
    "games",
    "minutes_per_game",
    "fgm",
    "fga",
    "ftm",
    "fta",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
)
BASE_POSITION_ORDER = ("PG", "SG", "SF", "PF", "C")
BASE_POSITION_SET = set(BASE_POSITION_ORDER)
TRUE_VALUES = {"1", "TRUE", "T", "YES", "Y"}
FALSE_VALUES = {"0", "FALSE", "F", "NO", "N"}


def validate_columns(columns: Iterable[str | None]) -> None:
    normalized_columns = {_normalize_column_name(column) for column in columns if column}
    missing = sorted(REQUIRED_COLUMNS - normalized_columns)
    if missing:
        raise ProjectionProviderValidationError(
            [f"missing required columns: {', '.join(missing)}"]
        )


def normalize_projection_players(
    records: Iterable[Mapping[str, object]],
) -> list[ProjectionPlayer]:
    errors: list[str] = []
    players: list[ProjectionPlayer] = []
    seen_ids: dict[str, int] = {}
    seen_names: dict[str, int] = {}

    for index, record in enumerate(records, start=1):
        normalized_record = {
            _normalize_column_name(key): value for key, value in record.items()
        }
        player = _normalize_projection_player(normalized_record, index, errors)
        if player is None:
            continue

        normalized_id = player.source_player_id.upper()
        normalized_name = player.full_name.casefold()
        if normalized_id in seen_ids:
            errors.append(
                f"row {index}: duplicate player_id '{player.source_player_id}' "
                f"also appears on row {seen_ids[normalized_id]}"
            )
        else:
            seen_ids[normalized_id] = index
        if normalized_name in seen_names:
            errors.append(
                f"row {index}: duplicate full_name '{player.full_name}' "
                f"also appears on row {seen_names[normalized_name]}"
            )
        else:
            seen_names[normalized_name] = index

        players.append(player)

    if not players and not errors:
        errors.append("projection provider returned no player rows")
    if errors:
        raise ProjectionProviderValidationError(errors)
    return players


def _normalize_projection_player(
    record: Mapping[str, object],
    row_number: int,
    errors: list[str],
) -> ProjectionPlayer | None:
    source_player_id = _required_text(record, "player_id", row_number, errors)
    full_name = _required_text(record, "full_name", row_number, errors)
    team = _optional_upper_text(record.get("team"))
    primary_position = _normalize_optional_position(
        record.get("primary_position"), "primary_position", row_number, errors
    )
    positions = _normalize_positions(
        record.get("positions"), primary_position, row_number, errors
    )
    is_active = _normalize_is_active(record.get("is_active"), row_number, errors)
    numeric_values = {
        field: _decimal_value(record.get(field), field, row_number, errors)
        for field in NUMERIC_FIELDS
    }

    if source_player_id is None or full_name is None or any(
        value is None for value in numeric_values.values()
    ):
        return None

    games = numeric_values["games"]
    minutes = numeric_values["minutes_per_game"]
    if games is not None and not Decimal("0") <= games <= Decimal("82"):
        errors.append(f"row {row_number}: games must be between 0 and 82")
    if minutes is not None and not Decimal("0") <= minutes <= Decimal("60"):
        errors.append(
            f"row {row_number}: minutes_per_game must be between 0 and 60"
        )
    for field in NUMERIC_FIELDS:
        value = numeric_values[field]
        if value is not None and value < 0:
            errors.append(f"row {row_number}: {field} must be nonnegative")
    if (
        numeric_values["fgm"] is not None
        and numeric_values["fga"] is not None
        and numeric_values["fgm"] > numeric_values["fga"]
    ):
        errors.append(f"row {row_number}: fgm cannot exceed fga")
    if (
        numeric_values["ftm"] is not None
        and numeric_values["fta"] is not None
        and numeric_values["ftm"] > numeric_values["fta"]
    ):
        errors.append(f"row {row_number}: ftm cannot exceed fta")

    return ProjectionPlayer(
        source_player_id=source_player_id,
        full_name=full_name,
        team=team,
        primary_position=primary_position,
        positions=positions,
        is_active=is_active,
        **{field: value for field, value in numeric_values.items() if value is not None},
    )


def _normalize_column_name(value: object) -> str:
    return str(value).strip().lower()


def _required_text(
    record: Mapping[str, object],
    field: str,
    row_number: int,
    errors: list[str],
) -> str | None:
    value = str(record.get(field) or "").strip()
    if not value:
        errors.append(f"row {row_number}: {field} is required")
        return None
    return value


def _optional_upper_text(value: object) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _normalize_optional_position(
    value: object,
    field: str,
    row_number: int,
    errors: list[str],
) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text not in BASE_POSITION_SET:
        errors.append(f"row {row_number}: {field} has unsupported position '{text}'")
        return None
    return text


def _normalize_positions(
    value: object,
    primary_position: str | None,
    row_number: int,
    errors: list[str],
) -> tuple[str, ...]:
    raw_positions = str(value or "").replace("/", ",").replace("|", ",")
    parts = [part.strip().upper() for part in raw_positions.split(",") if part.strip()]
    if not parts and primary_position:
        parts = [primary_position]
    positions = tuple(position for position in BASE_POSITION_ORDER if position in parts)
    unsupported = sorted(set(parts) - BASE_POSITION_SET)
    if unsupported:
        errors.append(
            f"row {row_number}: positions contain unsupported values: "
            f"{', '.join(unsupported)}"
        )
    if primary_position and primary_position not in positions:
        errors.append(
            f"row {row_number}: primary_position must be included in positions"
        )
    return positions


def _normalize_is_active(
    value: object,
    row_number: int,
    errors: list[str],
) -> bool:
    text = str(value).strip().upper() if value is not None else ""
    if not text:
        return True
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    errors.append(f"row {row_number}: is_active must be true or false")
    return True


def _decimal_value(
    value: object,
    field: str,
    row_number: int,
    errors: list[str],
) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        errors.append(f"row {row_number}: {field} is required")
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        errors.append(f"row {row_number}: {field} must be a valid decimal")
        return None
