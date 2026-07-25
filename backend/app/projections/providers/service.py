from __future__ import annotations

from app.projections.providers.base import ProjectionProvider
from app.projections.providers.csv_provider import CSVProjectionProvider
from app.projections.providers.models import ProjectionPlayer, ProjectionProviderPayload
from app.projections.providers.seed_provider import SeedProjectionProvider


class ProjectionProviderService:
    def __init__(self, default_provider: ProjectionProvider | None = None) -> None:
        self.default_provider = default_provider or SeedProjectionProvider()

    def load_players(
        self,
        provider: ProjectionProvider | None = None,
    ) -> list[ProjectionPlayer]:
        selected_provider = provider or self.default_provider
        return selected_provider.load_players()

    def load_csv_players(self, path: str) -> list[ProjectionPlayer]:
        return self.load_players(CSVProjectionProvider(path))

    def load_csv_payload(self, path: str) -> ProjectionProviderPayload:
        return CSVProjectionProvider(path).load_payload()
