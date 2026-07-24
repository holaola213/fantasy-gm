from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.leagues.model import League, RosterSlot, ScoringRule
from app.leagues.schemas import LeagueUpdate

SINGLETON_LEAGUE_ID = 1


class LeagueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_singleton_league(self) -> League | None:
        result = await self.session.scalars(
            select(League)
            .where(League.id == SINGLETON_LEAGUE_ID)
            .options(
                selectinload(League.scoring_rules),
                selectinload(League.roster_slots),
            )
            .execution_options(populate_existing=True)
        )
        return result.one_or_none()

    async def replace_singleton_league(self, payload: LeagueUpdate) -> League:
        league = await self.session.get(League, SINGLETON_LEAGUE_ID)
        if league is None:
            league = League(id=SINGLETON_LEAGUE_ID)
            self.session.add(league)

        league.name = payload.name
        league.platform = payload.platform
        league.season = payload.season
        league.team_count = payload.team_count
        league.scoring_format = payload.scoring_format
        league.acquisition_limit_per_day = payload.acquisition_limit_per_day
        league.playoff_team_count = payload.playoff_team_count

        await self.session.flush()

        await self.session.execute(
            delete(ScoringRule).where(ScoringRule.league_id == SINGLETON_LEAGUE_ID)
        )
        await self.session.execute(
            delete(RosterSlot).where(RosterSlot.league_id == SINGLETON_LEAGUE_ID)
        )

        self.session.add_all(
            [
                ScoringRule(
                    league_id=SINGLETON_LEAGUE_ID,
                    stat_key=rule.stat_key,
                    display_name=rule.display_name,
                    points=rule.points,
                    sort_order=rule.sort_order,
                )
                for rule in payload.scoring_rules
            ]
        )
        self.session.add_all(
            [
                RosterSlot(
                    league_id=SINGLETON_LEAGUE_ID,
                    slot_key=slot.slot_key,
                    display_name=slot.display_name,
                    count=slot.count,
                    sort_order=slot.sort_order,
                )
                for slot in payload.roster_slots
            ]
        )

        await self.session.flush()
        league = await self.get_singleton_league()
        if league is None:
            raise RuntimeError("league replacement failed")
        return league
