from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.leagues.model import League
from app.leagues.repository import LeagueRepository
from app.leagues.schemas import LeagueUpdate


class LeagueNotFoundError(Exception):
    pass


class LeaguePersistenceError(Exception):
    pass


class LeagueConfigurationLockedError(Exception):
    pass


class LeagueService:
    def __init__(self, repository: LeagueRepository, session: AsyncSession) -> None:
        self.repository = repository
        self.session = session

    async def get_league(self) -> League:
        league = await self.repository.get_singleton_league()
        if league is None:
            raise LeagueNotFoundError
        return league

    async def replace_league(self, payload: LeagueUpdate) -> League:
        try:
            async with self.session.begin():
                if await self.repository.active_draft_exists():
                    raise LeagueConfigurationLockedError
                return await self.repository.replace_singleton_league(payload)
        except LeagueConfigurationLockedError:
            raise
        except SQLAlchemyError as exc:
            raise LeaguePersistenceError from exc
