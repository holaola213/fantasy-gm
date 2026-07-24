from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.drafts.model import DraftPick, DraftSession, FantasyTeam
from app.leagues.model import League
from app.leagues.repository import SINGLETON_LEAGUE_ID
from app.players.model import PlayerEligibility


class DraftAssistantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current_in_progress_draft(self) -> DraftSession | None:
        result = await self.session.scalars(
            select(DraftSession)
            .where(DraftSession.league_id == SINGLETON_LEAGUE_ID)
            .where(DraftSession.status == "in_progress")
            .options(
                selectinload(DraftSession.teams),
                selectinload(DraftSession.picks).selectinload(DraftPick.player),
                selectinload(DraftSession.picks).selectinload(DraftPick.fantasy_team),
            )
            .execution_options(populate_existing=True)
            .order_by(DraftSession.created_at.desc(), DraftSession.id.desc())
        )
        return result.first()

    async def get_singleton_league(self) -> League | None:
        return await self.session.get(
            League,
            SINGLETON_LEAGUE_ID,
            options=[selectinload(League.roster_slots), selectinload(League.scoring_rules)],
        )

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
