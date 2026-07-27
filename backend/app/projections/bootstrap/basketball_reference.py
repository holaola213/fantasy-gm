from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.projections.providers.normalization import BASE_POSITION_ORDER


REQUIRED_SPS_COLUMNS = (
    "Rk",
    "Player",
    "Type",
    "FG",
    "FGA",
    "FT",
    "FTA",
    "TRB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PTS",
    "-9999",
)
REQUIRED_METADATA_COLUMNS = (
    "source_player_id",
    "player_name",
    "team",
    "primary_position",
    "positions",
)
BASE_POSITION_SET = set(BASE_POSITION_ORDER)


@dataclass(frozen=True)
class BasketballReferenceSpsPlayer:
    source_player_id: str
    full_name: str
    row_number: int
    projection_type: str
    fg_per36: Decimal
    fga_per36: Decimal
    ft_per36: Decimal
    fta_per36: Decimal
    rebounds_per36: Decimal
    assists_per36: Decimal
    steals_per36: Decimal
    blocks_per36: Decimal
    turnovers_per36: Decimal
    points_per36: Decimal


@dataclass(frozen=True)
class BasketballReferenceSpsIssue:
    code: str
    row_number: int | None
    player_name: str | None
    source_player_id: str | None
    field: str | None
    value: str | None
    message: str

    def __str__(self) -> str:
        parts: list[str] = []
        if self.row_number is not None:
            parts.append(f"row {self.row_number}")
        if self.player_name:
            parts.append(f"player '{self.player_name}'")
        if self.source_player_id:
            parts.append(f"basketball_reference_id '{self.source_player_id}'")
        if self.field:
            parts.append(f"field '{self.field}'")
        if self.value is not None:
            parts.append(f"value '{self.value}'")
        location = ": ".join(parts)
        return f"{location}: {self.message}" if location else self.message


@dataclass(frozen=True)
class BasketballReferenceSpsParseResult:
    rows_read: int
    accepted_players: tuple[BasketballReferenceSpsPlayer, ...]
    rejected_issues: tuple[BasketballReferenceSpsIssue, ...]

    @property
    def rejected_players(self) -> int:
        return len({issue.row_number for issue in self.rejected_issues if issue.row_number})

    @property
    def invalid_numeric_values(self) -> int:
        return sum(1 for issue in self.rejected_issues if issue.code == "invalid_numeric")

    @property
    def duplicate_ids(self) -> int:
        return sum(
            1
            for issue in self.rejected_issues
            if issue.code == "duplicate_basketball_reference_id"
        )


@dataclass(frozen=True)
class BasketballReferencePlayerMetadata:
    source_player_id: str
    player_name: str
    team: str
    primary_position: str
    positions: tuple[str, ...]
    row_number: int


@dataclass(frozen=True)
class BasketballReferenceMetadataParseResult:
    rows_read: int
    accepted_metadata: tuple[BasketballReferencePlayerMetadata, ...]
    rejected_issues: tuple[BasketballReferenceSpsIssue, ...]

    @property
    def metadata_available(self) -> bool:
        return bool(self.accepted_metadata) or any(
            issue.code != "metadata_file_not_found" for issue in self.rejected_issues
        )

    @property
    def rejected_rows(self) -> int:
        return len({issue.row_number for issue in self.rejected_issues if issue.row_number})

    @property
    def duplicate_ids(self) -> int:
        return sum(
            1
            for issue in self.rejected_issues
            if issue.code == "duplicate_metadata_source_id"
        )

    @property
    def invalid_teams(self) -> int:
        return sum(1 for issue in self.rejected_issues if issue.code == "invalid_team")

    @property
    def invalid_positions(self) -> int:
        return sum(
            1
            for issue in self.rejected_issues
            if issue.code in {"invalid_position", "primary_position_not_in_positions"}
        )


def parse_basketball_reference_sps_csv(
    path: str | Path,
) -> BasketballReferenceSpsParseResult:
    csv_path = Path(path)
    if not csv_path.exists():
        return BasketballReferenceSpsParseResult(
            rows_read=0,
            accepted_players=(),
            rejected_issues=(
                BasketballReferenceSpsIssue(
                    code="file_not_found",
                    row_number=None,
                    player_name=None,
                    source_player_id=None,
                    field=None,
                    value=str(csv_path),
                    message="Basketball Reference SPS CSV not found",
                ),
            ),
        )

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        rows = list(reader)

    if len(rows) < 2:
        return BasketballReferenceSpsParseResult(
            rows_read=0,
            accepted_players=(),
            rejected_issues=(
                BasketballReferenceSpsIssue(
                    code="missing_header",
                    row_number=None,
                    player_name=None,
                    source_player_id=None,
                    field=None,
                    value=None,
                    message="Basketball Reference SPS CSV is missing the data header",
                ),
            ),
        )

    header = rows[1]
    missing_columns = [column for column in REQUIRED_SPS_COLUMNS if column not in header]
    if missing_columns:
        return BasketballReferenceSpsParseResult(
            rows_read=0,
            accepted_players=(),
            rejected_issues=tuple(
                BasketballReferenceSpsIssue(
                    code="missing_required_column",
                    row_number=2,
                    player_name=None,
                    source_player_id=None,
                    field=column,
                    value=None,
                    message=f"missing required Basketball Reference SPS column: {column}",
                )
                for column in missing_columns
            ),
        )

    accepted_players: list[BasketballReferenceSpsPlayer] = []
    rejected_issues: list[BasketballReferenceSpsIssue] = []
    seen_ids: dict[str, int] = {}
    rows_read = 0

    for row_number, values in enumerate(rows[2:], start=3):
        if not any(value.strip() for value in values):
            continue
        rows_read += 1
        row = _row_dict(header, values)
        player_name = _text(row, "Player")
        source_player_id = _text(row, "-9999")
        row_issues: list[BasketballReferenceSpsIssue] = []

        if not player_name:
            row_issues.append(
                _issue("required_field_missing", row_number, None, source_player_id, "Player", None, "Player is required")
            )
        if not source_player_id:
            row_issues.append(
                _issue("required_field_missing", row_number, player_name, None, "-9999", None, "Basketball Reference player ID is required")
            )
        elif source_player_id in seen_ids:
            row_issues.append(
                _issue(
                    "duplicate_basketball_reference_id",
                    row_number,
                    player_name,
                    source_player_id,
                    "-9999",
                    source_player_id,
                    f"Basketball Reference player ID also appears on row {seen_ids[source_player_id]}",
                )
            )

        numeric_values: dict[str, Decimal] = {}
        for field in ("FG", "FGA", "FT", "FTA", "TRB", "AST", "STL", "BLK", "TOV", "PTS"):
            value = _decimal(row, field)
            if value is None:
                row_issues.append(
                    _issue(
                        "invalid_numeric",
                        row_number,
                        player_name,
                        source_player_id,
                        field,
                        row.get(field),
                        f"{field} must be a finite decimal",
                    )
                )
            else:
                numeric_values[field] = value

        if row_issues:
            rejected_issues.extend(row_issues)
            continue

        assert player_name is not None
        assert source_player_id is not None
        seen_ids[source_player_id] = row_number
        accepted_players.append(
            BasketballReferenceSpsPlayer(
                source_player_id=source_player_id,
                full_name=player_name,
                row_number=row_number,
                projection_type=_text(row, "Type") or "",
                fg_per36=numeric_values["FG"],
                fga_per36=numeric_values["FGA"],
                ft_per36=numeric_values["FT"],
                fta_per36=numeric_values["FTA"],
                rebounds_per36=numeric_values["TRB"],
                assists_per36=numeric_values["AST"],
                steals_per36=numeric_values["STL"],
                blocks_per36=numeric_values["BLK"],
                turnovers_per36=numeric_values["TOV"],
                points_per36=numeric_values["PTS"],
            )
        )

    return BasketballReferenceSpsParseResult(
        rows_read=rows_read,
        accepted_players=tuple(accepted_players),
        rejected_issues=tuple(rejected_issues),
    )


def parse_basketball_reference_metadata_csv(
    path: str | Path,
) -> BasketballReferenceMetadataParseResult:
    csv_path = Path(path)
    if not csv_path.exists():
        return BasketballReferenceMetadataParseResult(
            rows_read=0,
            accepted_metadata=(),
            rejected_issues=(
                BasketballReferenceSpsIssue(
                    code="metadata_file_not_found",
                    row_number=None,
                    player_name=None,
                    source_player_id=None,
                    field=None,
                    value=str(csv_path),
                    message="Basketball Reference player metadata CSV not found",
                ),
            ),
        )

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            return BasketballReferenceMetadataParseResult(
                rows_read=0,
                accepted_metadata=(),
                rejected_issues=(
                    BasketballReferenceSpsIssue(
                        code="missing_metadata_header",
                        row_number=None,
                        player_name=None,
                        source_player_id=None,
                        field=None,
                        value=None,
                        message="Basketball Reference metadata CSV is missing a header",
                    ),
                ),
            )
        normalized_columns = {_metadata_column(column) for column in reader.fieldnames}
        missing_columns = [
            column for column in REQUIRED_METADATA_COLUMNS if column not in normalized_columns
        ]
        if missing_columns:
            return BasketballReferenceMetadataParseResult(
                rows_read=0,
                accepted_metadata=(),
                rejected_issues=tuple(
                    BasketballReferenceSpsIssue(
                        code="missing_metadata_column",
                        row_number=1,
                        player_name=None,
                        source_player_id=None,
                        field=column,
                        value=None,
                        message=f"missing required Basketball Reference metadata column: {column}",
                    )
                    for column in missing_columns
                ),
            )

        accepted: list[BasketballReferencePlayerMetadata] = []
        rejected: list[BasketballReferenceSpsIssue] = []
        seen_ids: dict[str, int] = {}
        rows_read = 0
        for row_number, raw_row in enumerate(reader, start=2):
            row = {_metadata_column(key): (value or "").strip() for key, value in raw_row.items() if key}
            if not any(row.values()):
                continue
            rows_read += 1
            source_player_id = row.get("source_player_id", "").strip()
            player_name = row.get("player_name", "").strip()
            team = row.get("team", "").strip().upper()
            primary_position = row.get("primary_position", "").strip().upper()
            positions = _metadata_positions(row.get("positions", ""), primary_position)
            row_issues: list[BasketballReferenceSpsIssue] = []

            if not source_player_id:
                row_issues.append(
                    _issue(
                        "required_field_missing",
                        row_number,
                        player_name or None,
                        None,
                        "source_player_id",
                        None,
                        "source_player_id is required",
                    )
                )
            elif source_player_id in seen_ids:
                row_issues.append(
                    _issue(
                        "duplicate_metadata_source_id",
                        row_number,
                        player_name or None,
                        source_player_id,
                        "source_player_id",
                        source_player_id,
                        f"metadata source_player_id also appears on row {seen_ids[source_player_id]}",
                    )
                )
            if not player_name:
                row_issues.append(
                    _issue(
                        "required_field_missing",
                        row_number,
                        None,
                        source_player_id or None,
                        "player_name",
                        None,
                        "player_name is required",
                    )
                )
            if not team:
                row_issues.append(
                    _issue(
                        "invalid_team",
                        row_number,
                        player_name or None,
                        source_player_id or None,
                        "team",
                        row.get("team"),
                        "team is required",
                    )
                )
            if not primary_position or primary_position not in BASE_POSITION_SET:
                row_issues.append(
                    _issue(
                        "invalid_position",
                        row_number,
                        player_name or None,
                        source_player_id or None,
                        "primary_position",
                        primary_position or None,
                        "primary_position must be PG, SG, SF, PF, or C",
                    )
                )
            unsupported_positions = sorted(
                position for position in _metadata_position_parts(row.get("positions", "")) if position not in BASE_POSITION_SET
            )
            for position in unsupported_positions:
                row_issues.append(
                    _issue(
                        "invalid_position",
                        row_number,
                        player_name or None,
                        source_player_id or None,
                        "positions",
                        position,
                        "positions must contain only PG, SG, SF, PF, or C",
                    )
                )
            if not positions and not unsupported_positions:
                row_issues.append(
                    _issue(
                        "invalid_position",
                        row_number,
                        player_name or None,
                        source_player_id or None,
                        "positions",
                        row.get("positions"),
                        "positions is required",
                    )
                )
            elif primary_position and primary_position in BASE_POSITION_SET and primary_position not in positions:
                row_issues.append(
                    _issue(
                        "primary_position_not_in_positions",
                        row_number,
                        player_name or None,
                        source_player_id or None,
                        "primary_position",
                        primary_position,
                        "primary_position must be included in positions",
                    )
                )

            if row_issues:
                rejected.extend(row_issues)
                continue

            seen_ids[source_player_id] = row_number
            accepted.append(
                BasketballReferencePlayerMetadata(
                    source_player_id=source_player_id,
                    player_name=player_name,
                    team=team,
                    primary_position=primary_position,
                    positions=positions,
                    row_number=row_number,
                )
            )

    return BasketballReferenceMetadataParseResult(
        rows_read=rows_read,
        accepted_metadata=tuple(accepted),
        rejected_issues=tuple(rejected),
    )


def _row_dict(header: list[str], values: list[str]) -> dict[str, str]:
    return {
        column: values[index].strip() if index < len(values) else ""
        for index, column in enumerate(header)
    }


def _text(row: dict[str, str], field: str) -> str | None:
    value = row.get(field, "").strip()
    return value or None


def _metadata_column(value: str) -> str:
    return value.strip().lower()


def _metadata_position_parts(value: str) -> list[str]:
    raw = value.replace("/", ",").replace("|", ",")
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def _metadata_positions(value: str, primary_position: str) -> tuple[str, ...]:
    parts = _metadata_position_parts(value)
    if not parts and primary_position:
        parts = [primary_position]
    return tuple(position for position in BASE_POSITION_ORDER if position in parts)


def _decimal(row: dict[str, str], field: str) -> Decimal | None:
    value = row.get(field, "").strip()
    if not value:
        return None
    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _issue(
    code: str,
    row_number: int,
    player_name: str | None,
    source_player_id: str | None,
    field: str,
    value: str | None,
    message: str,
) -> BasketballReferenceSpsIssue:
    return BasketballReferenceSpsIssue(
        code=code,
        row_number=row_number,
        player_name=player_name,
        source_player_id=source_player_id,
        field=field,
        value=value,
        message=message,
    )
