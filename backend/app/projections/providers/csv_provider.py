from __future__ import annotations

import csv
from pathlib import Path

from app.projections.providers.base import ProjectionProvider
from app.projections.providers.models import ProjectionPlayer
from app.projections.providers.normalization import (
    normalize_projection_players,
    validate_columns,
)
from app.projections.providers.validation import ProjectionProviderValidationError


class CSVProjectionProvider(ProjectionProvider):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_players(self) -> list[ProjectionPlayer]:
        if not self.path.exists():
            raise ProjectionProviderValidationError(
                [f"projection CSV not found: {self.path}"]
            )

        with self.path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ProjectionProviderValidationError(["projection CSV is empty"])
            validate_columns(reader.fieldnames)
            return normalize_projection_players(reader)
