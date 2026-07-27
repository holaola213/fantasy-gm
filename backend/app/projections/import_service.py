from __future__ import annotations

from dataclasses import dataclass, field
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
from app.projections.providers.validation import (
    ProjectionProviderValidationError,
    ProjectionValidationIssue,
)
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
    "points",
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
class ProjectionPlayerImportPlan:
    source_player_id: str
    full_name: str
    player_id: int | None
    resolution: str
    identity_will_be_created: bool
    eligibility_positions_added: tuple[str, ...]
    eligibility_positions_removed: tuple[str, ...]

    @property
    def eligibility_will_change(self) -> bool:
        return bool(
            self.eligibility_positions_added or self.eligibility_positions_removed
        )


@dataclass(frozen=True)
class ProjectionImportPlan:
    source_key: str
    source_name: str
    season: int
    projection_type: str
    as_of_date: date
    rows_read: int
    valid_player_rows: int
    activation_requested: bool
    source_exists: bool
    player_plans: tuple[ProjectionPlayerImportPlan, ...]
    warnings: tuple[ProjectionValidationIssue, ...] = ()

    @property
    def matched_existing_players(self) -> int:
        return sum(1 for plan in self.player_plans if plan.player_id is not None)

    @property
    def newly_proposed_players(self) -> int:
        return sum(1 for plan in self.player_plans if plan.player_id is None)

    @property
    def identities_to_create(self) -> int:
        return sum(1 for plan in self.player_plans if plan.identity_will_be_created)

    @property
    def players_with_eligibility_changes(self) -> int:
        return sum(1 for plan in self.player_plans if plan.eligibility_will_change)

    @property
    def eligibility_positions_to_add(self) -> int:
        return sum(len(plan.eligibility_positions_added) for plan in self.player_plans)

    @property
    def eligibility_positions_to_remove(self) -> int:
        return sum(len(plan.eligibility_positions_removed) for plan in self.player_plans)

    @property
    def projection_rows_to_create(self) -> int:
        return self.valid_player_rows

@dataclass(frozen=True)
class ProjectionImportResult:
    projection_set_id: int
    source_key: str
    season: int
    as_of_date: date
    player_count: int
    is_active: bool
    source_name: str
    projection_type: str
    rows_imported: int
    existing_players_matched: int
    new_players_created: int
    source_identities_created: int
    players_with_eligibility_changes: int
    eligibility_positions_added: int
    eligibility_positions_removed: int
    projection_rows_created: int
    warnings: tuple[ProjectionValidationIssue, ...] = field(default_factory=tuple)


class ProjectionImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def preview_players(
        self,
        *,
        players: list[ProjectionPlayer],
        metadata: ProjectionImportMetadata,
        rows_read: int | None = None,
        warnings: tuple[ProjectionValidationIssue, ...] = (),
    ) -> ProjectionImportPlan:
        source_key = normalize_source_key(metadata.source_key)
        self._validate_metadata(metadata, source_key)
        self._validate_players(players)
        with self.session.no_autoflush:
            return await self._build_plan(
                players=players,
                metadata=metadata,
                source_key=source_key,
                rows_read=rows_read if rows_read is not None else len(players),
                warnings=warnings,
            )

    async def import_players(
        self,
        *,
        players: list[ProjectionPlayer],
        metadata: ProjectionImportMetadata,
        rows_read: int | None = None,
        warnings: tuple[ProjectionValidationIssue, ...] = (),
    ) -> ProjectionImportResult:
        source_key = normalize_source_key(metadata.source_key)
        self._validate_metadata(metadata, source_key)
        self._validate_players(players)
        if self.session.in_transaction():
            raise RuntimeError(
                "projection import requires a session with no active transaction; "
                "use a new session after preview"
            )

        async with self.session.begin():
            plan = await self._build_plan(
                players=players,
                metadata=metadata,
                source_key=source_key,
                rows_read=rows_read if rows_read is not None else len(players),
                warnings=warnings,
            )
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

            resolved_players = await self._persist_players(source, players, plan)
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
            source_name=source.name,
            season=metadata.season,
            projection_type=metadata.projection_type,
            as_of_date=metadata.as_of_date,
            player_count=len(players),
            rows_imported=plan.valid_player_rows,
            existing_players_matched=plan.matched_existing_players,
            new_players_created=plan.newly_proposed_players,
            source_identities_created=plan.identities_to_create,
            players_with_eligibility_changes=plan.players_with_eligibility_changes,
            eligibility_positions_added=plan.eligibility_positions_to_add,
            eligibility_positions_removed=plan.eligibility_positions_to_remove,
            projection_rows_created=plan.projection_rows_to_create,
            is_active=metadata.activate,
            warnings=plan.warnings,
        )

    async def _build_plan(
        self,
        *,
        players: list[ProjectionPlayer],
        metadata: ProjectionImportMetadata,
        source_key: str,
        rows_read: int,
        warnings: tuple[ProjectionValidationIssue, ...],
    ) -> ProjectionImportPlan:
        source = await self.session.scalar(
            select(ProjectionSource).where(ProjectionSource.key == source_key)
        )
        identities_by_source_id: dict[str, PlayerSourceIdentity] = {}
        if source is not None:
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
        existing_players_by_name = await self._players_by_exact_name(
            exact_names_without_identity
        )

        player_ids = {
            identity.player_id for identity in identities_by_source_id.values()
        } | {
            player.id
            for player in existing_players_by_name.values()
            if player is not None
        }
        eligibilities_by_player_id = await self._eligibilities_by_player_id(player_ids)

        player_plans: list[ProjectionPlayerImportPlan] = []
        for imported_player in players:
            identity = identities_by_source_id.get(imported_player.source_player_id)
            if identity is not None:
                resolution = "existing_identity"
                player_id = identity.player_id
            else:
                matched_player = existing_players_by_name.get(imported_player.full_name)
                resolution = "exact_name_match" if matched_player is not None else "new_player"
                player_id = matched_player.id if matched_player is not None else None

            existing_positions = (
                eligibilities_by_player_id.get(player_id, set())
                if player_id is not None
                else set()
            )
            imported_positions = set(imported_player.positions)
            player_plans.append(
                ProjectionPlayerImportPlan(
                    source_player_id=imported_player.source_player_id,
                    full_name=imported_player.full_name,
                    player_id=player_id,
                    resolution=resolution,
                    identity_will_be_created=identity is None,
                    eligibility_positions_added=tuple(
                        position
                        for position in BASE_POSITION_ORDER
                        if position in imported_positions - existing_positions
                    ),
                    eligibility_positions_removed=tuple(
                        position
                        for position in BASE_POSITION_ORDER
                        if position in existing_positions - imported_positions
                    ),
                )
            )

        return ProjectionImportPlan(
            source_key=source_key,
            source_name=metadata.source_name.strip(),
            season=metadata.season,
            projection_type=metadata.projection_type,
            as_of_date=metadata.as_of_date,
            rows_read=rows_read,
            valid_player_rows=len(players),
            activation_requested=metadata.activate,
            source_exists=source is not None,
            player_plans=tuple(player_plans),
            warnings=warnings,
        )

    async def _players_by_exact_name(
        self,
        names: set[str],
    ) -> dict[str, Player | None]:
        if not names:
            return {}

        existing_players = list(
            await self.session.scalars(select(Player).where(Player.full_name.in_(names)))
        )
        players_by_name: dict[str, Player | None] = {}
        for name in names:
            matches = [player for player in existing_players if player.full_name == name]
            if len(matches) > 1:
                raise ProjectionProviderValidationError(
                    [
                        ProjectionValidationIssue(
                            code="ambiguous_exact_name_match",
                            player_name=name,
                            message=(
                                "ambiguous exact player name match; provider identity "
                                "is required"
                            ),
                        )
                    ]
                )
            players_by_name[name] = matches[0] if matches else None
        return players_by_name

    async def _eligibilities_by_player_id(
        self,
        player_ids: set[int],
    ) -> dict[int, set[str]]:
        if not player_ids:
            return {}
        rows = await self.session.execute(
            select(PlayerEligibility.player_id, PlayerEligibility.position_key).where(
                PlayerEligibility.player_id.in_(player_ids)
            )
        )
        eligibilities: dict[int, set[str]] = {player_id: set() for player_id in player_ids}
        for player_id, position_key in rows:
            eligibilities.setdefault(player_id, set()).add(position_key)
        return eligibilities

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

    async def _persist_players(
        self,
        source: ProjectionSource,
        players: list[ProjectionPlayer],
        plan: ProjectionImportPlan,
    ) -> dict[str, Player]:
        plans_by_source_id = {player_plan.source_player_id: player_plan for player_plan in plan.player_plans}
        resolved: dict[str, Player] = {}
        for imported_player in players:
            player_plan = plans_by_source_id[imported_player.source_player_id]
            player = (
                await self.session.get(Player, player_plan.player_id)
                if player_plan.player_id is not None
                else None
            )
            if player is None:
                player = Player(full_name=imported_player.full_name)
                self.session.add(player)
                await self.session.flush()

            player.full_name = imported_player.full_name
            player.team = imported_player.team
            player.primary_position = imported_player.primary_position
            player.is_active = imported_player.is_active
            await self.session.flush()

            if player_plan.identity_will_be_created:
                self.session.add(
                    PlayerSourceIdentity(
                        source_id=source.id,
                        source_player_id=imported_player.source_player_id,
                        player_id=player.id,
                    )
                )

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
        errors: list[ProjectionValidationIssue] = []
        if not source_key:
            errors.append(
                ProjectionValidationIssue(
                    code="required_field_missing",
                    field="source_key",
                    message="source_key is required",
                )
            )
        if not metadata.source_name.strip():
            errors.append(
                ProjectionValidationIssue(
                    code="required_field_missing",
                    field="source_name",
                    message="source_name is required",
                )
            )
        if metadata.projection_type != "season":
            errors.append(
                ProjectionValidationIssue(
                    code="unsupported_projection_type",
                    field="projection_type",
                    value=metadata.projection_type,
                    message="projection_type must be season",
                )
            )
        if not 2000 <= metadata.season <= 2100:
            errors.append(
                ProjectionValidationIssue(
                    code="value_out_of_range",
                    field="season",
                    value=str(metadata.season),
                    message="season must be between 2000 and 2100",
                )
            )
        if errors:
            raise ProjectionProviderValidationError(errors)

    def _validate_players(self, players: list[ProjectionPlayer]) -> None:
        errors: list[str | ProjectionValidationIssue] = []
        if not players:
            errors.append("projection import requires at least one player")

        source_ids: dict[str, int] = {}
        for index, player in enumerate(players, start=1):
            normalized_id = player.source_player_id
            if normalized_id in source_ids:
                errors.append(
                    ProjectionValidationIssue(
                        code="duplicate_provider_player_id",
                        row_number=index,
                        source_player_id=player.source_player_id,
                        field="player_id",
                        value=player.source_player_id,
                        message=(
                            f"duplicate player_id '{player.source_player_id}' "
                            f"also appears on row {source_ids[normalized_id]}"
                        ),
                    )
                )
            else:
                source_ids[normalized_id] = index
            unsupported_positions = sorted(
                set(player.positions) - set(BASE_POSITION_ORDER)
            )
            for position in unsupported_positions:
                errors.append(
                    ProjectionValidationIssue(
                        code="unknown_position",
                        row_number=index,
                        player_name=player.full_name,
                        source_player_id=player.source_player_id,
                        field="positions",
                        value=position,
                        message=f"positions contain unsupported value: {position}",
                    )
                )
            for field, value in projection_values(player).items():
                if value is None:
                    continue
                if not isinstance(value, Decimal):
                    errors.append(f"row {index}: {field} must be a Decimal")
                elif not value.is_finite():
                    errors.append(
                        ProjectionValidationIssue(
                            code="non_finite_number",
                            row_number=index,
                            player_name=player.full_name,
                            source_player_id=player.source_player_id,
                            field=field,
                            value=str(value),
                            message=f"{field} must be a finite decimal",
                        )
                    )

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
