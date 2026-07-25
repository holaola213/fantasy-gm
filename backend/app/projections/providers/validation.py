from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectionValidationIssue:
    code: str
    message: str
    row_number: int | None = None
    player_name: str | None = None
    source_player_id: str | None = None
    field: str | None = None
    value: str | None = None

    def __str__(self) -> str:
        parts: list[str] = []
        if self.row_number is not None:
            parts.append(f"row {self.row_number}")
        if self.player_name:
            parts.append(f"player '{self.player_name}'")
        if self.source_player_id:
            parts.append(f"player_id '{self.source_player_id}'")
        if self.field:
            parts.append(f"field '{self.field}'")
        if self.value is not None:
            parts.append(f"value '{self.value}'")
        location = ": ".join(parts)
        return f"{location}: {self.message}" if location else self.message


class ProjectionProviderValidationError(ValueError):
    def __init__(
        self,
        errors: list[str | ProjectionValidationIssue],
    ) -> None:
        self.issues = [
            error
            if isinstance(error, ProjectionValidationIssue)
            else ProjectionValidationIssue(code="validation_error", message=error)
            for error in errors
        ]
        self.errors = [str(issue) for issue in self.issues]
        super().__init__("; ".join(self.errors))
