from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

from app.drafts.compatibility import (
    BASE_POSITION_KEYS,
    compatible_roster_slots,
)
from app.leagues.model import League
from app.players.model import Player
from app.projections.model import PlayerProjection, ProjectionSet
from app.shared.scoring import FantasyScorer
from app.valuations.replacement import (
    BASE_POSITION_ORDER,
    InsufficientEligiblePlayerPoolError,
    ReplacementLevel,
    UnsupportedRosterSlotError,
    ValuationCandidate,
    calculate_replacement_levels,
)
from app.valuations.repository import ValuationRepository
from app.valuations.schemas import (
    ActiveSlotDemandRead,
    DiagnosticMetadataRead,
    DiagnosticPlayerRead,
    DiagnosticProjectionRead,
    DiagnosticReplacementLevelRead,
    DiagnosticReplacementRead,
    DiagnosticScoringContributionRead,
    DiagnosticScoringRead,
    DiagnosticScoringRuleRead,
    DiagnosticUnsupportedScoringRuleRead,
    PlayerValuationRead,
    PlayerValuationDiagnosticsResponse,
    PositionValueRead,
    ReplacementLevelRead,
    ReplacementLevelsResponse,
)

VALUATION_ALGORITHM_VERSION = "replacement-v2"
VALUATION_CACHE_MAX_ENTRIES = 8
ValuationCacheKey = tuple[int, str, int, str, str, int, str | None]


class LeagueConfigurationRequiredError(Exception):
    pass


class ActiveProjectionSetRequiredError(Exception):
    pass


class ProjectionSetNotFoundError(Exception):
    pass


class DraftRequiredError(Exception):
    pass


class ConflictingProjectionSetError(Exception):
    pass


class PlayerValuationNotFoundError(Exception):
    pass


class PlayerProjectionNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class _ValuationContext:
    league: League
    projection_set: ProjectionSet
    draft_id: int | None


@dataclass(frozen=True)
class _ValuationSnapshot:
    items: list[PlayerValuationRead]
    levels: dict[str, ReplacementLevel]
    demand: dict[str, int]
    drafted_target: int


_valuation_cache: OrderedDict[ValuationCacheKey, _ValuationSnapshot] = OrderedDict()
_valuation_in_flight: dict[ValuationCacheKey, asyncio.Task[_ValuationSnapshot]] = {}
_latest_league_configuration_fingerprints: dict[int, str] = {}


@dataclass(frozen=True)
class _ValuationSeed:
    player: Player
    projection: PlayerProjection
    eligible_positions: tuple[str, ...]
    compatible_slots: list[str]
    fantasy_points_per_game: Decimal
    projected_fantasy_points: Decimal

    @property
    def normalized_name(self) -> str:
        return self.player.full_name.casefold()


class ValuationService:
    def __init__(self, repository: ValuationRepository) -> None:
        self.repository = repository

    async def list_valuations(
        self,
        *,
        projection_set_id: int | None,
        available_only: bool,
        search: str | None,
        team: str | None,
        position: str | None,
        sort: str,
        direction: str,
        limit: int,
        offset: int,
    ) -> tuple[list[PlayerValuationRead], int, ProjectionSet]:
        context = await self._context(
            projection_set_id=projection_set_id,
            available_only=available_only,
        )
        all_items = await self._all_valuations(context)
        if available_only:
            drafted_ids = await self.repository.drafted_player_ids(context.draft_id or 0)
            all_items = [item for item in all_items if item.player_id not in drafted_ids]
        filtered = self._filter_items(all_items, search=search, team=team, position=position)
        sorted_items = self._sort_items(filtered, sort=sort, direction=direction)
        return sorted_items[offset : offset + limit], len(filtered), context.projection_set

    async def replacement_levels(
        self,
        *,
        projection_set_id: int | None,
    ) -> ReplacementLevelsResponse:
        context = await self._context(
            projection_set_id=projection_set_id,
            available_only=False,
        )
        snapshot = await self._valuation_snapshot(context)
        return ReplacementLevelsResponse(
            projection_set_id=context.projection_set.id,
            projection_set_name=context.projection_set.name,
            projection_set_as_of_date=context.projection_set.as_of_date,
            team_count=context.league.team_count,
            active_slot_demand=[
                ActiveSlotDemandRead(slot_key=slot_key, count=count)
                for slot_key, count in sorted(snapshot.demand.items())
            ],
            total_active_demand=sum(snapshot.demand.values()),
            drafted_player_target=snapshot.drafted_target,
            positions=[
                ReplacementLevelRead(
                    position=position,
                    demand=snapshot.levels[position].demand,
                    replacement_player_id=snapshot.levels[position].replacement_player_id,
                    replacement_player_name=snapshot.levels[position].replacement_player_name,
                    replacement_fantasy_points=snapshot.levels[
                        position
                    ].replacement_fantasy_points,
                )
                for position in BASE_POSITION_ORDER
            ],
        )

    async def player_valuation(
        self,
        *,
        player_id: int,
        projection_set_id: int | None,
    ) -> PlayerValuationRead:
        context = await self._context(
            projection_set_id=projection_set_id,
            available_only=False,
        )
        for item in await self._all_valuations(context):
            if item.player_id == player_id:
                return item
        raise PlayerValuationNotFoundError

    async def player_diagnostics(
        self,
        *,
        player_id: int,
        projection_set_id: int | None,
    ) -> PlayerValuationDiagnosticsResponse:
        context = await self._context(
            projection_set_id=projection_set_id,
            available_only=False,
        )
        row = await self.repository.get_projection_player(
            projection_set_id=context.projection_set.id,
            player_id=player_id,
        )
        if row is None:
            raise PlayerProjectionNotFoundError
        player, projection = row
        eligibilities = await self.repository.get_eligibilities_by_player_ids([player.id])
        valuation = await self.player_valuation(
            player_id=player.id,
            projection_set_id=context.projection_set.id,
        )
        best_position_value = self._best_position(valuation.position_values)
        scoring = self._diagnostic_scoring(
            league=context.league,
            projection=projection,
        )
        return PlayerValuationDiagnosticsResponse(
            player=DiagnosticPlayerRead(
                id=player.id,
                name=player.full_name,
                team=player.team,
                primary_position=player.primary_position,
                eligible_positions=eligibilities.get(player.id, []),
            ),
            projection=DiagnosticProjectionRead(
                projection_set_id=context.projection_set.id,
                games=projection.games,
                minutes_per_game=projection.minutes_per_game,
                raw_projected_stats={
                    "fgm": projection.fgm,
                    "fga": projection.fga,
                    "ftm": projection.ftm,
                    "fta": projection.fta,
                    "rebounds": projection.rebounds,
                    "assists": projection.assists,
                    "steals": projection.steals,
                    "blocks": projection.blocks,
                    "turnovers": projection.turnovers,
                    "points": projection.points,
                },
            ),
            scoring=scoring,
            replacement=DiagnosticReplacementRead(
                calculation_method=(
                    "VOR is projected fantasy total minus the replacement-level "
                    "projected total for each eligible base position; overall VOR "
                    "uses the best eligible position value."
                ),
                replacement_levels=[
                    DiagnosticReplacementLevelRead(
                        position=value.position,
                        replacement_player_id=value.replacement_player_id,
                        replacement_player_name=value.replacement_player_name,
                        replacement_fantasy_points=value.replacement_fantasy_points,
                        vor=value.vor,
                        position_rank=value.position_rank,
                    )
                    for value in valuation.position_values
                ],
                selected_replacement_position=best_position_value.position
                if best_position_value
                else None,
                selected_replacement_player_id=best_position_value.replacement_player_id
                if best_position_value
                else None,
                selected_replacement_player_name=best_position_value.replacement_player_name
                if best_position_value
                else None,
                selected_replacement_fantasy_points=best_position_value.replacement_fantasy_points
                if best_position_value
                else None,
                overall_vor=valuation.overall_vor,
            ),
            metadata=DiagnosticMetadataRead(
                league_id=context.league.id,
                projection_set_id=context.projection_set.id,
                valuation_algorithm_version=VALUATION_ALGORITHM_VERSION,
                scoring_format=context.league.scoring_format,
                assumptions=[
                    "These values reflect the current bootstrap projection assumptions when bootstrap data is active.",
                    "Projected total equals Fantasy PPG multiplied by projected games.",
                    "No scoring, replacement-level, VOR, ranking, recommendation, or draft formula is changed by diagnostics.",
                ],
            ),
        )

    async def _context(
        self,
        *,
        projection_set_id: int | None,
        available_only: bool,
    ) -> _ValuationContext:
        league = await self.repository.get_singleton_league()
        if league is None:
            raise LeagueConfigurationRequiredError

        draft = await self.repository.get_current_draft()
        if available_only:
            if draft is None:
                raise DraftRequiredError
            if projection_set_id is not None and projection_set_id != draft.projection_set_id:
                raise ConflictingProjectionSetError
            projection_set_id = draft.projection_set_id

        if projection_set_id is None and draft is not None:
            projection_set_id = draft.projection_set_id

        if projection_set_id is not None:
            projection_set = await self.repository.get_projection_set(projection_set_id)
            if projection_set is None:
                raise ProjectionSetNotFoundError
        else:
            projection_set = await self.repository.get_deterministic_active_projection_set()
            if projection_set is None:
                raise ActiveProjectionSetRequiredError

        return _ValuationContext(
            league=league,
            projection_set=projection_set,
            draft_id=draft.id if draft else None,
        )

    async def _all_valuations(self, context: _ValuationContext) -> list[PlayerValuationRead]:
        snapshot = await self._valuation_snapshot(context)
        return list(snapshot.items)

    async def _valuation_snapshot(self, context: _ValuationContext) -> _ValuationSnapshot:
        cache_key = await self._cache_key(context)
        self._clear_stale_league_entries(cache_key)
        cached = _valuation_cache.get(cache_key)
        if cached is not None:
            _valuation_cache.move_to_end(cache_key)
            return cached

        in_flight = _valuation_in_flight.get(cache_key)
        if in_flight is not None:
            return await in_flight

        task = asyncio.create_task(self._compute_valuation_snapshot(context))
        _valuation_in_flight[cache_key] = task
        try:
            snapshot = await task
        finally:
            if _valuation_in_flight.get(cache_key) is task:
                _valuation_in_flight.pop(cache_key, None)
        _valuation_cache[cache_key] = snapshot
        _valuation_cache.move_to_end(cache_key)
        while len(_valuation_cache) > VALUATION_CACHE_MAX_ENTRIES:
            _valuation_cache.popitem(last=False)
        return snapshot

    async def _cache_key(self, context: _ValuationContext) -> ValuationCacheKey:
        eligibility_count, latest_eligibility = (
            await self.repository.projection_eligibility_fingerprint(
                context.projection_set.id
            )
        )
        return (
            context.league.id,
            self._league_configuration_fingerprint(context.league),
            context.projection_set.id,
            context.projection_set.imported_at.isoformat(),
            VALUATION_ALGORITHM_VERSION,
            eligibility_count,
            latest_eligibility.isoformat() if latest_eligibility else None,
        )

    def _clear_stale_league_entries(self, cache_key: ValuationCacheKey) -> None:
        league_id, league_fingerprint = cache_key[0], cache_key[1]
        latest_fingerprint = _latest_league_configuration_fingerprints.get(league_id)
        if latest_fingerprint == league_fingerprint:
            return
        for existing_key in list(_valuation_cache):
            if existing_key[0] == league_id:
                _valuation_cache.pop(existing_key, None)
        for existing_key in list(_valuation_in_flight):
            if existing_key[0] == league_id:
                _valuation_in_flight.pop(existing_key, None)
        _latest_league_configuration_fingerprints[league_id] = league_fingerprint

    def _league_configuration_fingerprint(self, league: League) -> str:
        scoring_parts = [
            f"{rule.stat_key}:{rule.points}:{rule.sort_order}"
            for rule in sorted(league.scoring_rules, key=lambda item: item.stat_key)
        ]
        slot_parts = [
            f"{slot.slot_key}:{slot.count}:{slot.sort_order}"
            for slot in sorted(league.roster_slots, key=lambda item: item.slot_key)
        ]
        return "|".join(
            [
                league.platform,
                str(league.season),
                str(league.team_count),
                league.scoring_format,
                str(league.acquisition_limit_per_day),
                str(league.playoff_team_count),
                ",".join(scoring_parts),
                ",".join(slot_parts),
            ]
        )

    def _diagnostic_scoring(
        self,
        *,
        league: League,
        projection: PlayerProjection,
    ) -> DiagnosticScoringRead:
        scorer = FantasyScorer(league.scoring_rules)
        contributions = scorer.contributions(projection)
        fantasy_points_per_game = sum(
            (item.contribution for item in contributions),
            Decimal("0"),
        )
        return DiagnosticScoringRead(
            rules=[
                DiagnosticScoringRuleRead(
                    stat_key=rule.stat_key,
                    display_name=rule.display_name,
                    points=rule.points,
                    sort_order=rule.sort_order,
                )
                for rule in sorted(league.scoring_rules, key=lambda item: item.sort_order)
            ],
            contributions=[
                DiagnosticScoringContributionRead(
                    stat_name=item.stat_name,
                    scoring_key=item.scoring_key,
                    configured_stat_key=item.configured_stat_key,
                    is_configured=item.configured_stat_key is not None,
                    projection_value=item.projection_value,
                    league_weight=item.league_weight,
                    contribution=item.contribution,
                )
                for item in contributions
            ],
            unsupported_rules=[
                DiagnosticUnsupportedScoringRuleRead(
                    stat_key=item.stat_key,
                    points=item.points,
                    message=item.message,
                )
                for item in scorer.unsupported_rules
            ],
            fantasy_points_per_game=fantasy_points_per_game,
            projected_fantasy_points=fantasy_points_per_game * projection.games,
        )

    async def _compute_valuation_snapshot(
        self,
        context: _ValuationContext,
    ) -> _ValuationSnapshot:
        seeds = await self._seeds(context)
        levels, demand, drafted_target, _ = calculate_replacement_levels(
            candidates=self._candidates(seeds),
            roster_slot_counts=self._roster_slot_counts(context.league),
            team_count=context.league.team_count,
        )
        items = [self._read(seed, levels) for seed in seeds]
        self._assign_ranks(items)
        return _ValuationSnapshot(
            items=items,
            levels=levels,
            demand=demand,
            drafted_target=drafted_target,
        )

    async def _seeds(self, context: _ValuationContext) -> list[_ValuationSeed]:
        rows = await self.repository.list_projection_players(context.projection_set.id)
        player_ids = [player.id for player, _ in rows]
        eligibilities = await self.repository.get_eligibilities_by_player_ids(player_ids)
        configured_slots = self._configured_slots(context.league)
        scorer = FantasyScorer(context.league.scoring_rules)
        seeds = []
        for player, projection in rows:
            positions = tuple(eligibilities.get(player.id, []))
            fppg = scorer.fantasy_points_per_game(projection)
            seeds.append(
                _ValuationSeed(
                    player=player,
                    projection=projection,
                    eligible_positions=positions,
                    compatible_slots=compatible_roster_slots(list(positions), configured_slots),
                    fantasy_points_per_game=fppg,
                    projected_fantasy_points=fppg * projection.games,
                )
            )
        return seeds

    def _candidates(self, seeds: list[_ValuationSeed]) -> list[ValuationCandidate]:
        return [
            ValuationCandidate(
                player_id=seed.player.id,
                player_name=seed.player.full_name,
                projected_fantasy_points=seed.projected_fantasy_points,
                fantasy_points_per_game=seed.fantasy_points_per_game,
                eligible_positions=seed.eligible_positions,
            )
            for seed in seeds
            if seed.eligible_positions
        ]

    def _read(
        self,
        seed: _ValuationSeed,
        levels: dict[str, ReplacementLevel],
    ) -> PlayerValuationRead:
        position_values = []
        for position in seed.eligible_positions:
            if position not in BASE_POSITION_KEYS:
                continue
            level = levels[position]
            position_values.append(
                PositionValueRead(
                    position=position,
                    replacement_player_id=level.replacement_player_id,
                    replacement_player_name=level.replacement_player_name,
                    replacement_fantasy_points=level.replacement_fantasy_points,
                    vor=seed.projected_fantasy_points - level.replacement_fantasy_points,
                    position_rank=0,
                )
            )
        best = self._best_position(position_values)
        return PlayerValuationRead(
            player_id=seed.player.id,
            player_name=seed.player.full_name,
            team=seed.player.team,
            primary_position=seed.player.primary_position,
            eligible_positions=list(seed.eligible_positions),
            compatible_roster_slots=seed.compatible_slots,
            projected_games=seed.projection.games,
            fantasy_points_per_game=seed.fantasy_points_per_game,
            projected_fantasy_points=seed.projected_fantasy_points,
            position_values=position_values,
            overall_vor=best.vor if best else None,
            best_value_position=best.position if best else None,
            overall_rank=None,
        )

    def _assign_ranks(self, items: list[PlayerValuationRead]) -> None:
        ranked = sorted(items, key=self._overall_rank_key)
        for rank, item in enumerate(ranked, start=1):
            if item.overall_vor is not None:
                item.overall_rank = rank

        for position in BASE_POSITION_ORDER:
            position_values = [
                (item, value)
                for item in items
                for value in item.position_values
                if value.position == position
            ]
            position_values.sort(key=lambda pair: self._position_rank_key(pair[0], pair[1]))
            for rank, (_, value) in enumerate(position_values, start=1):
                value.position_rank = rank

    def _overall_rank_key(self, item: PlayerValuationRead):
        return (
            item.overall_vor is None,
            -(item.overall_vor or Decimal("-999999999")),
            -item.projected_fantasy_points,
            -item.fantasy_points_per_game,
            item.player_name.casefold(),
            item.player_id,
        )

    def _position_rank_key(self, item: PlayerValuationRead, value: PositionValueRead):
        return (
            -value.vor,
            -item.projected_fantasy_points,
            -item.fantasy_points_per_game,
            item.player_name.casefold(),
            item.player_id,
        )

    def _filter_items(
        self,
        items: list[PlayerValuationRead],
        *,
        search: str | None,
        team: str | None,
        position: str | None,
    ) -> list[PlayerValuationRead]:
        filtered = items
        if search:
            needle = search.casefold()
            filtered = [item for item in filtered if needle in item.player_name.casefold()]
        if team:
            normalized_team = team.casefold()
            filtered = [
                item for item in filtered if (item.team or "").casefold() == normalized_team
            ]
        if position:
            normalized_position = position.upper()
            filtered = [
                item for item in filtered if normalized_position in item.eligible_positions
            ]
        return filtered

    def _sort_items(
        self,
        items: list[PlayerValuationRead],
        *,
        sort: str,
        direction: str,
    ) -> list[PlayerValuationRead]:
        reverse = direction == "desc"
        if sort == "overall_rank":
            if direction == "desc":
                return sorted(
                    items,
                    key=lambda item: (
                        item.overall_rank is None,
                        -(item.overall_rank or -999999999),
                        item.player_name.casefold(),
                        item.player_id,
                    ),
                )
            return sorted(
                items,
                key=lambda item: (
                    item.overall_rank is None,
                    item.overall_rank or 999999999,
                    item.player_name.casefold(),
                    item.player_id,
                ),
                reverse=False,
            )
        sort_key = {
            "player": lambda item: item.player_name.casefold(),
            "team": lambda item: (item.team or "").casefold(),
            "position": lambda item: item.primary_position or "",
            "fantasy_points_per_game": lambda item: item.fantasy_points_per_game,
            "projected_fantasy_points": lambda item: item.projected_fantasy_points,
            "overall_vor": lambda item: item.overall_vor
            if item.overall_vor is not None
            else Decimal("-999999999"),
        }[sort]
        return sorted(
            sorted(items, key=lambda item: (item.player_name.casefold(), item.player_id)),
            key=sort_key,
            reverse=reverse,
        )

    def _best_position(
        self, position_values: list[PositionValueRead]
    ) -> PositionValueRead | None:
        if not position_values:
            return None
        return sorted(
            position_values,
            key=lambda value: (-value.vor, BASE_POSITION_ORDER.index(value.position)),
        )[0]

    def _roster_slot_counts(self, league: League) -> dict[str, int]:
        return {slot.slot_key: slot.count for slot in league.roster_slots}

    def _configured_slots(self, league: League) -> list[str]:
        return [
            slot.slot_key
            for slot in sorted(league.roster_slots, key=lambda item: item.sort_order)
            if slot.count > 0 and slot.slot_key != "IR"
        ]
