from sqlalchemy import Select, asc, delete, desc, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.drafts.model import DraftPick, DraftSession, FantasyTeam
from app.leagues.model import League
from app.leagues.repository import SINGLETON_LEAGUE_ID
from app.players.model import Player, PlayerEligibility
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource


class DraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current_draft(self) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.league_id == SINGLETON_LEAGUE_ID)
            .where(DraftSession.status.in_(("setup", "in_progress")))
            .options(
                selectinload(DraftSession.teams),
                selectinload(DraftSession.picks).selectinload(DraftPick.player),
                selectinload(DraftSession.picks).selectinload(DraftPick.fantasy_team),
            )
            .execution_options(populate_existing=True)
            .order_by(DraftSession.created_at.desc(), DraftSession.id.desc())
        )
        return result.first()

    async def get_current_draft_for_update(self) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.league_id == SINGLETON_LEAGUE_ID)
            .where(DraftSession.status.in_(("setup", "in_progress")))
            .with_for_update()
            .options(
                selectinload(DraftSession.teams),
                selectinload(DraftSession.picks).selectinload(DraftPick.player),
                selectinload(DraftSession.picks).selectinload(DraftPick.fantasy_team),
            )
            .execution_options(populate_existing=True)
            .order_by(DraftSession.created_at.desc(), DraftSession.id.desc())
        )
        return result.first()

    async def get_latest_draft(self) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.league_id == SINGLETON_LEAGUE_ID)
            .options(
                selectinload(DraftSession.teams),
                selectinload(DraftSession.picks).selectinload(DraftPick.player),
                selectinload(DraftSession.picks).selectinload(DraftPick.fantasy_team),
            )
            .execution_options(populate_existing=True)
            .order_by(DraftSession.created_at.desc(), DraftSession.id.desc())
        )
        return result.first()

    async def get_latest_draft_for_update(self) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.league_id == SINGLETON_LEAGUE_ID)
            .with_for_update()
            .options(
                selectinload(DraftSession.teams),
                selectinload(DraftSession.picks).selectinload(DraftPick.player),
                selectinload(DraftSession.picks).selectinload(DraftPick.fantasy_team),
            )
            .execution_options(populate_existing=True)
            .order_by(DraftSession.created_at.desc(), DraftSession.id.desc())
        )
        return result.first()

    async def get_draft(self, draft_session_id: int) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.id == draft_session_id)
            .options(
                selectinload(DraftSession.teams),
                selectinload(DraftSession.picks).selectinload(DraftPick.player),
                selectinload(DraftSession.picks).selectinload(DraftPick.fantasy_team),
            )
            .execution_options(populate_existing=True)
        )
        return result.one_or_none()

    async def get_singleton_league(self) -> League | None:
        return await self.session.get(
            League,
            SINGLETON_LEAGUE_ID,
            options=[selectinload(League.roster_slots), selectinload(League.scoring_rules)],
        )

    async def get_deterministic_active_projection_set(self) -> ProjectionSet | None:
        result = await self.session.scalars(
            select(ProjectionSet)
            .join(ProjectionSource)
            .where(ProjectionSource.is_active.is_(True))
            .where(ProjectionSet.is_active.is_(True))
            .order_by(
                ProjectionSource.key,
                ProjectionSet.season.desc(),
                ProjectionSet.as_of_date.desc(),
                ProjectionSet.imported_at.desc(),
                ProjectionSet.id,
            )
        )
        return result.first()

    async def create_draft_session(
        self,
        *,
        league_id: int,
        projection_set_id: int,
        name: str,
        season: int,
        team_count: int,
        rounds: int,
    ) -> DraftSession:
        draft = DraftSession(
            league_id=league_id,
            projection_set_id=projection_set_id,
            name=name,
            season=season,
            draft_type="snake",
            status="setup",
            team_count=team_count,
            rounds=rounds,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def replace_teams(
        self,
        *,
        draft_session_id: int,
        teams: list[FantasyTeam],
    ) -> None:
        await self.session.execute(
            delete(FantasyTeam).where(FantasyTeam.draft_session_id == draft_session_id)
        )
        self.session.add_all(teams)
        await self.session.flush()

    async def delete_draft(self, draft: DraftSession) -> None:
        await self.session.delete(draft)
        await self.session.flush()

    async def delete_draft_picks(self, draft_session_id: int) -> None:
        await self.session.execute(
            delete(DraftPick).where(DraftPick.draft_session_id == draft_session_id)
        )
        await self.session.flush()

    async def get_team_by_position(
        self,
        *,
        draft_session_id: int,
        draft_position: int,
    ) -> FantasyTeam | None:
        result = await self.session.scalars(
            select(FantasyTeam).where(
                FantasyTeam.draft_session_id == draft_session_id,
                FantasyTeam.draft_position == draft_position,
            )
        )
        return result.one_or_none()

    async def get_team(
        self,
        *,
        draft_session_id: int,
        fantasy_team_id: int,
    ) -> FantasyTeam | None:
        result = await self.session.scalars(
            select(FantasyTeam).where(
                FantasyTeam.draft_session_id == draft_session_id,
                FantasyTeam.id == fantasy_team_id,
            )
        )
        return result.one_or_none()

    async def count_picks(self, draft_session_id: int) -> int:
        return (
            await self.session.scalar(
                select(func.count()).select_from(DraftPick).where(
                    DraftPick.draft_session_id == draft_session_id
                )
            )
            or 0
        )

    async def player_is_available(
        self,
        *,
        draft: DraftSession,
        player_id: int,
    ) -> bool:
        query = (
            select(Player.id)
            .join(PlayerProjection, PlayerProjection.player_id == Player.id)
            .where(Player.id == player_id)
            .where(Player.is_active.is_(True))
            .where(PlayerProjection.projection_set_id == draft.projection_set_id)
            .where(
                ~exists().where(
                    DraftPick.draft_session_id == draft.id,
                    DraftPick.player_id == Player.id,
                )
            )
        )
        return await self.session.scalar(query) is not None

    async def get_player_eligibilities(self, player_id: int) -> list[str]:
        result = await self.session.scalars(
            select(PlayerEligibility.position_key)
            .where(PlayerEligibility.player_id == player_id)
            .order_by(PlayerEligibility.position_key)
        )
        return list(result.all())

    async def create_pick(
        self,
        *,
        draft_session_id: int,
        fantasy_team_id: int,
        player_id: int,
        round_number: int,
        pick_in_round: int,
        overall_pick: int,
    ) -> DraftPick:
        pick = DraftPick(
            draft_session_id=draft_session_id,
            fantasy_team_id=fantasy_team_id,
            player_id=player_id,
            round_number=round_number,
            pick_in_round=pick_in_round,
            overall_pick=overall_pick,
        )
        self.session.add(pick)
        await self.session.flush()
        return pick

    async def get_latest_pick(self, draft_session_id: int) -> DraftPick | None:
        result = await self.session.scalars(
            select(DraftPick)
            .where(DraftPick.draft_session_id == draft_session_id)
            .order_by(DraftPick.overall_pick.desc())
            .limit(1)
        )
        return result.one_or_none()

    async def delete_pick(self, pick: DraftPick) -> None:
        await self.session.delete(pick)
        await self.session.flush()

    async def list_available_players(
        self,
        *,
        draft: DraftSession,
        search: str | None,
        team: str | None,
        position: str | None,
        sort: str,
        direction: str,
        limit: int | None,
        offset: int,
    ) -> tuple[list[tuple[Player, PlayerProjection]], int]:
        filtered_query = self._apply_available_filters(
            select(Player, PlayerProjection).join(
                PlayerProjection, PlayerProjection.player_id == Player.id
            ),
            draft=draft,
            search=search,
            team=team,
            position=position,
        )
        total_query = self._apply_available_filters(
            select(func.count()).select_from(Player).join(
                PlayerProjection, PlayerProjection.player_id == Player.id
            ),
            draft=draft,
            search=search,
            team=team,
            position=position,
        )
        total = await self.session.scalar(total_query)
        ordered_query = self._apply_sort(filtered_query, sort=sort, direction=direction)
        if limit is not None:
            ordered_query = ordered_query.limit(limit).offset(offset)
        result = await self.session.execute(ordered_query)
        return list(result.all()), total or 0

    def _apply_available_filters(
        self,
        query: Select,
        *,
        draft: DraftSession,
        search: str | None,
        team: str | None,
        position: str | None,
    ) -> Select:
        query = query.where(Player.is_active.is_(True))
        query = query.where(PlayerProjection.projection_set_id == draft.projection_set_id)
        query = query.where(
            ~exists().where(
                DraftPick.draft_session_id == draft.id,
                DraftPick.player_id == Player.id,
            )
        )
        if search:
            query = query.where(Player.full_name.ilike(f"%{search}%"))
        if team:
            query = query.where(func.lower(Player.team) == team.lower())
        if position:
            query = query.where(
                exists().where(
                    PlayerEligibility.player_id == Player.id,
                    func.lower(PlayerEligibility.position_key) == position.lower(),
                )
            )
        return query

    def _apply_sort(self, query: Select, *, sort: str, direction: str) -> Select:
        sort_columns = {
            "player": Player.full_name,
            "team": Player.team,
            "position": Player.primary_position,
        }
        column = sort_columns.get(sort, Player.full_name)
        primary_order = desc(column) if direction == "desc" else asc(column)
        return query.order_by(primary_order, Player.full_name, Player.id)
