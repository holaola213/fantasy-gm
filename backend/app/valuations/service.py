from __future__ import annotations

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
    PlayerValuationRead,
    PositionValueRead,
    ReplacementLevelRead,
    ReplacementLevelsResponse,
)


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


@dataclass(frozen=True)
class _ValuationContext:
    league: League
    projection_set: ProjectionSet
    draft_id: int | None


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
        seeds = await self._seeds(context)
        levels, demand, drafted_target, _ = calculate_replacement_levels(
            candidates=self._candidates(seeds),
            roster_slot_counts=self._roster_slot_counts(context.league),
            team_count=context.league.team_count,
        )
        return ReplacementLevelsResponse(
            projection_set_id=context.projection_set.id,
            projection_set_name=context.projection_set.name,
            projection_set_as_of_date=context.projection_set.as_of_date,
            team_count=context.league.team_count,
            active_slot_demand=[
                ActiveSlotDemandRead(slot_key=slot_key, count=count)
                for slot_key, count in sorted(demand.items())
            ],
            total_active_demand=sum(demand.values()),
            drafted_player_target=drafted_target,
            positions=[
                ReplacementLevelRead(
                    position=position,
                    demand=levels[position].demand,
                    replacement_player_id=levels[position].replacement_player_id,
                    replacement_player_name=levels[position].replacement_player_name,
                    replacement_fantasy_points=levels[position].replacement_fantasy_points,
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
        seeds = await self._seeds(context)
        levels, _, _, _ = calculate_replacement_levels(
            candidates=self._candidates(seeds),
            roster_slot_counts=self._roster_slot_counts(context.league),
            team_count=context.league.team_count,
        )
        items = [self._read(seed, levels) for seed in seeds]
        self._assign_ranks(items)
        return items

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
