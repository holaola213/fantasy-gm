from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.drafts.model import DraftPick, DraftSession
from app.leagues.model import League
from app.leagues.repository import SINGLETON_LEAGUE_ID
from app.players.model import Player, PlayerEligibility
from app.projections.model import PlayerProjection, ProjectionSet, ProjectionSource


class ValuationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_singleton_league(self) -> League | None:
        return await self.session.get(
            League,
            SINGLETON_LEAGUE_ID,
            options=[selectinload(League.scoring_rules), selectinload(League.roster_slots)],
        )

    async def get_projection_set(self, projection_set_id: int) -> ProjectionSet | None:
        return await self.session.get(
            ProjectionSet,
            projection_set_id,
            options=[selectinload(ProjectionSet.source)],
        )

    async def get_current_draft(self) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.league_id == SINGLETON_LEAGUE_ID)
            .where(DraftSession.status.in_(("setup", "in_progress")))
            .order_by(DraftSession.created_at.desc(), DraftSession.id.desc())
        )
        return result.first()

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
            .options(selectinload(ProjectionSet.source))
        )
        return result.first()

    async def list_projection_players(
        self, projection_set_id: int
    ) -> list[tuple[Player, PlayerProjection]]:
        result = await self.session.execute(
            select(Player, PlayerProjection)
            .join(PlayerProjection, PlayerProjection.player_id == Player.id)
            .where(PlayerProjection.projection_set_id == projection_set_id)
            .where(Player.is_active.is_(True))
            .order_by(Player.full_name, Player.id)
        )
        return list(result.all())

    async def get_projection_player(
        self,
        *,
        projection_set_id: int,
        player_id: int,
    ) -> tuple[Player, PlayerProjection] | None:
        result = await self.session.execute(
            select(Player, PlayerProjection)
            .join(PlayerProjection, PlayerProjection.player_id == Player.id)
            .where(PlayerProjection.projection_set_id == projection_set_id)
            .where(Player.id == player_id)
            .where(Player.is_active.is_(True))
        )
        return result.one_or_none()

    async def get_eligibilities_by_player_ids(
        self, player_ids: list[int]
    ) -> dict[int, list[str]]:
        if not player_ids:
            return {}
        result = await self.session.execute(
            select(PlayerEligibility.player_id, PlayerEligibility.position_key)
            .where(PlayerEligibility.player_id.in_(player_ids))
            .order_by(PlayerEligibility.player_id, PlayerEligibility.position_key)
        )
        eligibilities: dict[int, list[str]] = {player_id: [] for player_id in player_ids}
        for player_id, position_key in result.all():
            eligibilities.setdefault(player_id, []).append(position_key)
        return eligibilities

    async def projection_eligibility_fingerprint(
        self,
        projection_set_id: int,
    ) -> tuple[int, datetime | None]:
        result = await self.session.execute(
            select(
                func.count(PlayerEligibility.id),
                func.max(PlayerEligibility.created_at),
            )
            .join(PlayerProjection, PlayerProjection.player_id == PlayerEligibility.player_id)
            .where(PlayerProjection.projection_set_id == projection_set_id)
        )
        count, latest_created_at = result.one()
        return int(count or 0), latest_created_at

    async def drafted_player_ids(self, draft_session_id: int) -> set[int]:
        result = await self.session.scalars(
            select(DraftPick.player_id).where(DraftPick.draft_session_id == draft_session_id)
        )
        return set(result.all())

    async def active_draft_exists(self) -> bool:
        query = select(
            exists().where(
                DraftSession.league_id == SINGLETON_LEAGUE_ID,
                DraftSession.status.in_(("setup", "in_progress")),
            )
        )
        return bool(await self.session.scalar(query))
