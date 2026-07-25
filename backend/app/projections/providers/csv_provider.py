from __future__ import annotations

import csv
from pathlib import Path

from app.projections.providers.base import ProjectionProvider
from app.projections.providers.models import ProjectionPlayer, ProjectionProviderPayload
from app.projections.providers.normalization import (
    INTERNAL_ROW_NUMBER_KEY,
    normalize_projection_players,
    unknown_column_issues,
    validate_columns,
)
from app.projections.providers.validation import (
    ProjectionProviderValidationError,
    ProjectionValidationIssue,
)


class CSVProjectionProvider(ProjectionProvider):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_players(self) -> list[ProjectionPlayer]:
        return self.load_payload().players

    def load_payload(self) -> ProjectionProviderPayload:
        if not self.path.exists():
            raise ProjectionProviderValidationError(
                [f"projection CSV not found: {self.path}"]
            )

        with self.path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ProjectionProviderValidationError(["projection CSV is empty"])
            validate_columns(reader.fieldnames)
            warnings = unknown_column_issues(reader.fieldnames)
            records: list[dict[str, object]] = []
            errors: list[ProjectionValidationIssue] = []
            for csv_row_number, row in enumerate(reader, start=2):
                if not _has_content(row):
                    continue
                if None in row:
                    overflow_value = ",".join(
                        str(value) for value in row[None] if value is not None
                    )
                    errors.append(
                        ProjectionValidationIssue(
                            code="malformed_row",
                            row_number=csv_row_number,
                            value=overflow_value,
                            message=(
                                "CSV row contains more fields than the header defines"
                            ),
                        )
                    )
                    continue
                record = dict(row)
                record[INTERNAL_ROW_NUMBER_KEY] = csv_row_number
                records.append(record)
            if errors:
                raise ProjectionProviderValidationError(errors)

            return ProjectionProviderPayload(
                players=normalize_projection_players(records),
                rows_read=len(records),
                warnings=warnings,
            )


def _has_content(row: dict[str, object]) -> bool:
    return any(str(value or "").strip() for value in row.values())
