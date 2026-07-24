from __future__ import annotations

from typing import Protocol

from app.projections.providers.models import ProjectionPlayer


class ProjectionProvider(Protocol):
    def load_players(self) -> list[ProjectionPlayer]:
        """Return normalized projection players from the provider source."""
