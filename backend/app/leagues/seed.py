from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.leagues.model import League, RosterSlot, ScoringRule
from app.leagues.repository import SINGLETON_LEAGUE_ID
from app.leagues.schemas import normalize_key
from app.shared.database.session import AsyncSessionLocal


@dataclass(frozen=True)
class ScoringRuleFixture:
    stat_key: str
    display_name: str
    points: Decimal
    sort_order: int


@dataclass(frozen=True)
class RosterSlotFixture:
    slot_key: str
    display_name: str
    count: int
    sort_order: int


# Local development fixture keys only. They are not ESPN identifiers.
SCORING_RULE_FIXTURES = [
    ScoringRuleFixture("FGM", "Field Goals Made", Decimal("1"), 1),
    ScoringRuleFixture("FGA", "Field Goals Attempted", Decimal("-1"), 2),
    ScoringRuleFixture("FTM", "Free Throws Made", Decimal("1"), 3),
    ScoringRuleFixture("FTA", "Free Throws Attempted", Decimal("-1"), 4),
    ScoringRuleFixture("REB", "Rebounds", Decimal("1"), 5),
    ScoringRuleFixture("AST", "Assists", Decimal("1"), 6),
    ScoringRuleFixture("STL", "Steals", Decimal("2"), 7),
    ScoringRuleFixture("BLK", "Blocks", Decimal("2"), 8),
    ScoringRuleFixture("TO", "Turnovers", Decimal("-1"), 9),
]


# Counts confirmed from the development ESPN roster view.
ROSTER_SLOT_FIXTURES = [
    RosterSlotFixture("PG", "Point Guard", 1, 1),
    RosterSlotFixture("SG", "Shooting Guard", 1, 2),
    RosterSlotFixture("SF", "Small Forward", 1, 3),
    RosterSlotFixture("PF", "Power Forward", 1, 4),
    RosterSlotFixture("C", "Center", 1, 5),
    RosterSlotFixture("G", "Guard", 1, 6),
    RosterSlotFixture("F", "Forward", 1, 7),
    RosterSlotFixture("UTIL", "Utility", 3, 8),
    RosterSlotFixture("BE", "Bench", 4, 9),
    RosterSlotFixture("IR", "Injured Reserve", 2, 10),
]


async def seed_league() -> int:
    async with AsyncSessionLocal() as session:
        league_statement = insert(League).values(
            id=SINGLETON_LEAGUE_ID,
            name="Fantasy GM Development League",
            platform="ESPN",
            season=2026,
            team_count=12,
            scoring_format="points",
            acquisition_limit_per_day=1,
            playoff_team_count=8,
        )
        league_statement = league_statement.on_conflict_do_update(
            index_elements=[League.id],
            set_={
                "name": league_statement.excluded.name,
                "platform": league_statement.excluded.platform,
                "season": league_statement.excluded.season,
                "team_count": league_statement.excluded.team_count,
                "scoring_format": league_statement.excluded.scoring_format,
                "acquisition_limit_per_day": (
                    league_statement.excluded.acquisition_limit_per_day
                ),
                "playoff_team_count": league_statement.excluded.playoff_team_count,
                "updated_at": func.now(),
            },
        )
        await session.execute(league_statement)

        scoring_rows = [
            {
                "league_id": SINGLETON_LEAGUE_ID,
                "stat_key": normalize_key(fixture.stat_key),
                "display_name": fixture.display_name,
                "points": fixture.points,
                "sort_order": fixture.sort_order,
            }
            for fixture in SCORING_RULE_FIXTURES
        ]
        scoring_statement = insert(ScoringRule).values(scoring_rows)
        scoring_statement = scoring_statement.on_conflict_do_update(
            index_elements=[ScoringRule.league_id, ScoringRule.stat_key],
            set_={
                "display_name": scoring_statement.excluded.display_name,
                "points": scoring_statement.excluded.points,
                "sort_order": scoring_statement.excluded.sort_order,
            },
        )
        await session.execute(scoring_statement)

        roster_rows = [
            {
                "league_id": SINGLETON_LEAGUE_ID,
                "slot_key": normalize_key(fixture.slot_key),
                "display_name": fixture.display_name,
                "count": fixture.count,
                "sort_order": fixture.sort_order,
            }
            for fixture in ROSTER_SLOT_FIXTURES
        ]
        roster_statement = insert(RosterSlot).values(roster_rows)
        roster_statement = roster_statement.on_conflict_do_update(
            index_elements=[RosterSlot.league_id, RosterSlot.slot_key],
            set_={
                "display_name": roster_statement.excluded.display_name,
                "count": roster_statement.excluded.count,
                "sort_order": roster_statement.excluded.sort_order,
            },
        )
        await session.execute(roster_statement)

        await session.commit()

    return 1


async def main() -> None:
    await seed_league()
    print("Seeded singleton local development league configuration.")


if __name__ == "__main__":
    asyncio.run(main())
