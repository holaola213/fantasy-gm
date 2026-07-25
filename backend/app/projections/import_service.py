from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.players.model import Player, PlayerEligibility
from app.projections.model import (
    PlayerProjection,
    PlayerSourceIdentity,
    ProjectionSet,
    ProjectionSource,
)
from app.projections.providers import ProjectionPlayer
from app.projections.providers.normalization import BASE_POSITION_ORDER
from app.projections.providers.validation import ProjectionProviderValidationError
from app.projections.schemas import normalize_source_key


PROJECTION_FIELDS = (
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


@dataclass(frozen=True)
class ProjectionImportMetadata:
    source_key: str
    source_name: str
    season: int
    as_of_date: date
    source_description: str | None = None
    projection_type: str = "season"
    activate: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class ProjectionImportResult:
    projection_set_id: int
    source_key: str
    season: int
    as_of_date: date
    player_count: int
    is_active: bool


class ProjectionImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_players(
        self,
        *,
        players: list[ProjectionPlayer],
        metadata: ProjectionImportMetadata,
    ) -> ProjectionImportResult:
        source_key = normalize_source_key(metadata.source_key)
        self._validate_metadata(metadata, source_key)
        self._validate_players(players)

        async with self.session.begin():
            source = await self._resolve_source(
                key=source_key,
                name=metadata.source_name.strip(),
                description=metadata.source_description,
            )
            if metadata.activate:
                await self.session.execute(
                    update(ProjectionSet)
                    .where(
                        ProjectionSet.source_id == source.id,
                        ProjectionSet.season == metadata.season,
                        ProjectionSet.projection_type == metadata.projection_type,
                        ProjectionSet.is_active.is_(True),
                    )
                    .values(is_active=False)
                )

            projection_set = ProjectionSet(
                source_id=source.id,
                name=self._projection_set_name(metadata, source.name),
                season=metadata.season,
                projection_type=metadata.projection_type,
                as_of_date=metadata.as_of_date,
                is_active=metadata.activate,
                notes=metadata.notes,
            )
            self.session.add(projection_set)
            await self.session.flush()

            resolved_players = await self._resolve_players(source, players)
            self.session.add_all(
                [
                    PlayerProjection(
                        projection_set_id=projection_set.id,
                        player_id=resolved_players[player.source_player_id].id,
                        **projection_values(player),
                    )
                    for player in players
                ]
            )
            await self.session.flush()

        return ProjectionImportResult(
            projection_set_id=projection_set.id,
            source_key=source.key,
            season=metadata.season,
            as_of_date=metadata.as_of_date,
            player_count=len(players),
            is_active=metadata.activate,
        )

    async def _resolve_source(
        self,
        *,
        key: str,
        name: str,
        description: str | None,
    ) -> ProjectionSource:
        source = await self.session.scalar(
            select(ProjectionSource).where(ProjectionSource.key == key)
        )
        if source is None:
            source = ProjectionSource(
                key=key,
                name=name,
                description=description,
                is_active=True,
            )
            self.session.add(source)
            await self.session.flush()
            return source

        source.name = name
        source.description = description
        source.updated_at = func.now()
        await self.session.flush()
        return source

    async def _resolve_players(
        self,
        source: ProjectionSource,
        players: list[ProjectionPlayer],
    ) -> dict[str, Player]:
        identity_rows = list(
            await self.session.scalars(
                select(PlayerSourceIdentity).where(
                    PlayerSourceIdentity.source_id == source.id,
                    PlayerSourceIdentity.source_player_id.in_(
                        [player.source_player_id for player in players]
                    ),
                )
            )
        )
        identities_by_source_id = {
            identity.source_player_id: identity for identity in identity_rows
        }

        exact_names_without_identity = {
            player.full_name
            for player in players
            if player.source_player_id not in identities_by_source_id
        }
        existing_players_by_name: dict[str, Player | None] = {}
        if exact_names_without_identity:
            existing_players = list(
                await self.session.scalars(
                    select(Player).where(Player.full_name.in_(exact_names_without_identity))
                )
            )
            for name in exact_names_without_identity:
                matches = [
                    player for player in existing_players if player.full_name == name
                ]
                if len(matches) > 1:
                    raise ProjectionProviderValidationError(
                        [
                            "ambiguous exact player name match for "
                            f"'{name}'; provider identity is required"
                        ]
                    )
                existing_players_by_name[name] = matches[0] if matches else None

        resolved: dict[str, Player] = {}
        for imported_player in players:
            identity = identities_by_source_id.get(imported_player.source_player_id)
            player = (
                await self.session.get(Player, identity.player_id)
                if identity
                else None
            )
            if player is None:
                player = existing_players_by_name.get(imported_player.full_name)
            if player is None:
                player = Player(full_name=imported_player.full_name)
                self.session.add(player)
                await self.session.flush()

            player.full_name = imported_player.full_name
            player.team = imported_player.team
            player.primary_position = imported_player.primary_position
            player.is_active = imported_player.is_active
            await self.session.flush()

            if identity is None:
                identity = PlayerSourceIdentity(
                    source_id=source.id,
                    source_player_id=imported_player.source_player_id,
                    player_id=player.id,
                )
                self.session.add(identity)

            await self._persist_eligibilities(player, imported_player.positions)
            resolved[imported_player.source_player_id] = player

        await self.session.flush()
        return resolved

    async def _persist_eligibilities(
        self,
        player: Player,
        positions: tuple[str, ...],
    ) -> None:
        existing_positions = set(
            await self.session.scalars(
                select(PlayerEligibility.position_key).where(
                    PlayerEligibility.player_id == player.id
                )
            )
        )
        imported_positions = set(positions)
        obsolete_positions = existing_positions - imported_positions
        if obsolete_positions:
            await self.session.execute(
                delete(PlayerEligibility).where(
                    PlayerEligibility.player_id == player.id,
                    PlayerEligibility.position_key.in_(obsolete_positions),
                )
            )
        for position in positions:
            if position not in existing_positions:
                self.session.add(
                    PlayerEligibility(player_id=player.id, position_key=position)
                )

    def _validate_metadata(
        self,
        metadata: ProjectionImportMetadata,
        source_key: str,
    ) -> None:
        errors: list[str] = []
        if not source_key:
            errors.append("source_key is required")
        if not metadata.source_name.strip():
            errors.append("source_name is required")
        if metadata.projection_type != "season":
            errors.append("projection_type must be season")
        if not 2000 <= metadata.season <= 2100:
            errors.append("season must be between 2000 and 2100")
        if errors:
            raise ProjectionProviderValidationError(errors)

    def _validate_players(self, players: list[ProjectionPlayer]) -> None:
        errors: list[str] = []
        if not players:
            errors.append("projection import requires at least one player")

        source_ids: dict[str, int] = {}
        for index, player in enumerate(players, start=1):
            normalized_id = player.source_player_id
            if normalized_id in source_ids:
                errors.append(
                    f"row {index}: duplicate player_id '{player.source_player_id}' "
                    f"also appears on row {source_ids[normalized_id]}"
                )
            else:
                source_ids[normalized_id] = index
            unsupported_positions = sorted(
                set(player.positions) - set(BASE_POSITION_ORDER)
            )
            if unsupported_positions:
                errors.append(
                    f"row {index}: positions contain unsupported values: "
                    f"{', '.join(unsupported_positions)}"
                )
            for field, value in projection_values(player).items():
                if not isinstance(value, Decimal):
                    errors.append(f"row {index}: {field} must be a Decimal")

        if errors:
            raise ProjectionProviderValidationError(errors)

    def _projection_set_name(
        self,
        metadata: ProjectionImportMetadata,
        source_name: str,
    ) -> str:
        return f"{source_name} {metadata.season} {metadata.projection_type} {metadata.as_of_date}"


def projection_values(player: ProjectionPlayer) -> dict[str, Decimal]:
    return {field: getattr(player, field) for field in PROJECTION_FIELDS}
