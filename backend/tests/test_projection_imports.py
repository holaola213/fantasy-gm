from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.drafts.model import DraftSession
from app.leagues.model import League
from app.main import app
from app.players.model import Player, PlayerEligibility
from app.projections.import_service import (
    ProjectionImportMetadata,
    ProjectionImportService,
)
from app.projections.model import (
    PlayerProjection,
    PlayerSourceIdentity,
    ProjectionSet,
)
from app.projections.providers import (
    CSVProjectionProvider,
    ProjectionProviderService,
    ProjectionProviderValidationError,
)
from app.projections.providers.models import ProjectionPlayer
from app.shared.config.settings import get_settings
from app.shared.database.base import Base
from app.shared.database.session import get_session


@pytest_asyncio.fixture()
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    database_url = settings.database_url
    schema_name = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(database_url)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    await admin_engine.dispose()

    engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield factory
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await engine.dispose()


@pytest_asyncio.fixture()
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_alembic_upgrade_created_active_projection_set_partial_index() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            index_row = (
                await connection.execute(
                    text(
                        """
                        SELECT
                            ix.indisunique AS is_unique,
                            array_agg(att.attname ORDER BY ord.ordinality) AS columns,
                            pg_get_expr(ix.indpred, ix.indrelid) AS predicate
                        FROM pg_class idx
                        JOIN pg_index ix ON ix.indexrelid = idx.oid
                        JOIN pg_class tbl ON tbl.oid = ix.indrelid
                        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
                        JOIN unnest(ix.indkey) WITH ORDINALITY AS ord(attnum, ordinality)
                            ON true
                        JOIN pg_attribute att
                            ON att.attrelid = tbl.oid
                            AND att.attnum = ord.attnum
                        WHERE ns.nspname = current_schema()
                        AND tbl.relname = 'projection_sets'
                        AND idx.relname = 'uq_projection_sets_one_active_per_source_season_type'
                        GROUP BY ix.indisunique, ix.indpred, ix.indrelid
                        """
                    )
                )
            ).one_or_none()
            old_constraint_exists = await connection.scalar(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_projection_sets_source_season_type_as_of'
                    )
                    """
                )
            )
    finally:
        await engine.dispose()

    assert index_row is not None
    assert index_row.is_unique is True
    assert index_row.columns == ["source_id", "season", "projection_type"]
    assert index_row.predicate == "(is_active = true)"
    assert old_constraint_exists is False


def test_guarded_downgrade_checks_duplicates_before_schema_mutation(monkeypatch) -> None:
    migration = load_projection_import_migration()
    calls: list[str] = []

    class FakeConnection:
        def scalar(self, statement):
            calls.append("scalar")
            assert "HAVING count(*) > 1" in str(statement)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeConnection())
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda *args, **kwargs: calls.append("drop_index"),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda *args, **kwargs: calls.append("drop_table"),
    )
    monkeypatch.setattr(
        migration.op,
        "create_unique_constraint",
        lambda *args, **kwargs: calls.append("create_unique_constraint"),
    )

    with pytest.raises(RuntimeError, match="duplicate projection snapshots"):
        migration.downgrade()

    assert calls == ["scalar"]


def test_normal_downgrade_runs_schema_mutations_after_duplicate_check(monkeypatch) -> None:
    migration = load_projection_import_migration()
    calls: list[str] = []

    class FakeConnection:
        def scalar(self, statement):
            calls.append("scalar")
            assert "GROUP BY source_id, season, projection_type, as_of_date" in str(
                statement
            )
            return 0

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeConnection())
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, **kwargs: calls.append(f"drop_index:{name}"),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda name: calls.append(f"drop_table:{name}"),
    )
    monkeypatch.setattr(
        migration.op,
        "create_unique_constraint",
        lambda name, *args, **kwargs: calls.append(f"create_unique_constraint:{name}"),
    )

    migration.downgrade()

    assert calls == [
        "scalar",
        "drop_index:uq_projection_sets_one_active_per_source_season_type",
        "drop_table:player_source_identities",
        "create_unique_constraint:uq_projection_sets_source_season_type_as_of",
    ]


@pytest.mark.asyncio
async def test_successful_normalized_player_import_creates_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        result = await import_players(session, [sample_player()])

    async with session_factory() as session:
        projection_set = await session.get(ProjectionSet, result.projection_set_id)
        projection_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerProjection)
        )
        identity_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerSourceIdentity)
        )

    assert result.player_count == 1
    assert result.is_active is False
    assert projection_set is not None
    assert projection_set.is_active is False
    assert projection_count == 1
    assert identity_count == 1


@pytest.mark.asyncio
async def test_csv_to_database_import(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path,
) -> None:
    csv_path = tmp_path / "projection.csv"
    csv_path.write_text(
        "player_id,full_name,team,primary_position,positions,games,minutes_per_game,"
        "fgm,fga,ftm,fta,rebounds,assists,steals,blocks,turnovers\n"
        "csv-1,CSV Player,DEN,C,C,68.5,31.25,7.125,13.250,4,5,9,3,1,2,2\n",
        encoding="utf-8",
    )
    players = ProjectionProviderService().load_players(CSVProjectionProvider(csv_path))

    async with session_factory() as session:
        result = await import_players(
            session,
            players,
            metadata=metadata(source_key="csv", source_name="CSV Source"),
        )

    async with session_factory() as session:
        projection = await session.scalar(
            select(PlayerProjection).where(
                PlayerProjection.projection_set_id == result.projection_set_id
            )
        )
        player = await session.scalar(select(Player).where(Player.full_name == "CSV Player"))

    assert projection is not None
    assert player is not None
    assert projection.player_id == player.id
    assert projection.games == Decimal("68.50")
    assert projection.minutes_per_game == Decimal("31.25")


@pytest.mark.asyncio
async def test_every_successful_import_creates_new_projection_set(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_players(session, [sample_player()])
        second = await import_players(session, [sample_player()])

    assert first.projection_set_id != second.projection_set_id

    async with session_factory() as session:
        set_count = await session.scalar(select(text("count(*)")).select_from(ProjectionSet))
    assert set_count == 2


@pytest.mark.asyncio
async def test_existing_projection_sets_and_rows_remain_unchanged(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_players(
            session,
            [sample_player(fgm=Decimal("1.000"), fga=Decimal("2.000"))],
        )
        second = await import_players(
            session,
            [sample_player(fgm=Decimal("3.000"), fga=Decimal("4.000"))],
        )

    async with session_factory() as session:
        old_projection = await session.scalar(
            select(PlayerProjection).where(
                PlayerProjection.projection_set_id == first.projection_set_id
            )
        )
        new_projection = await session.scalar(
            select(PlayerProjection).where(
                PlayerProjection.projection_set_id == second.projection_set_id
            )
        )

    assert old_projection is not None
    assert new_projection is not None
    assert old_projection.fgm == Decimal("1.000")
    assert new_projection.fgm == Decimal("3.000")


@pytest.mark.asyncio
async def test_player_creation_existing_resolution_and_decimal_preservation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_players(
            session,
            [sample_player(team="DEN", games=Decimal("68.50"))],
        )
        second = await import_players(
            session,
            [sample_player(team="OKC", games=Decimal("70.25"))],
        )

    async with session_factory() as session:
        players = list(await session.scalars(select(Player)))
        projections = list(
            await session.scalars(
                select(PlayerProjection).order_by(PlayerProjection.projection_set_id)
            )
        )

    assert len(players) == 1
    assert players[0].team == "OKC"
    assert [projection.projection_set_id for projection in projections] == [
        first.projection_set_id,
        second.projection_set_id,
    ]
    assert projections[0].games == Decimal("68.50")
    assert projections[1].games == Decimal("70.25")


@pytest.mark.asyncio
async def test_eligibility_persistence_without_duplicates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(session, [sample_player(positions=("PG", "SG"))])
        await import_players(session, [sample_player(positions=("PG", "SG"))])

    async with session_factory() as session:
        positions = list(
            await session.scalars(
                select(PlayerEligibility.position_key).order_by(
                    PlayerEligibility.position_key
                )
            )
        )

    assert positions == ["PG", "SG"]


@pytest.mark.asyncio
async def test_import_replaces_obsolete_eligibility_positions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(session, [sample_player(positions=("PG", "SG"))])
        await import_players(session, [sample_player(positions=("SG",))])

    assert await eligibility_positions(session_factory) == ["SG"]


@pytest.mark.asyncio
async def test_import_can_add_back_replaced_eligibility_positions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(session, [sample_player(positions=("SG",))])
        await import_players(session, [sample_player(positions=("PG", "SG"))])

    assert await eligibility_positions(session_factory) == ["PG", "SG"]


@pytest.mark.asyncio
async def test_failed_import_rolls_back_eligibility_replacement(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(session, [sample_player(positions=("PG", "SG"))])

    async with session_factory() as session:
        with pytest.raises(Exception):
            await import_players(
                session,
                [
                    sample_player(
                        positions=("SG",),
                        fgm=Decimal("4.000"),
                        fga=Decimal("3.000"),
                    )
                ],
            )

    assert await eligibility_positions(session_factory) == ["PG", "SG"]


@pytest.mark.asyncio
async def test_duplicate_source_ids_fail_before_persistence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ProjectionProviderValidationError, match="duplicate player_id"):
            await import_players(
                session,
                [
                    sample_player(source_player_id="dup", full_name="Player One"),
                    sample_player(source_player_id="dup", full_name="Player Two"),
                ],
            )

    async with session_factory() as session:
        source_count = await session.scalar(
            select(text("count(*)")).select_from(ProjectionSet)
        )
    assert source_count == 0


@pytest.mark.asyncio
async def test_duplicate_source_ids_are_case_sensitive_within_import(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(
            session,
            [
                sample_player(source_player_id="dup", full_name="Player One"),
                sample_player(source_player_id="DUP", full_name="Player Two"),
            ],
        )

    async with session_factory() as session:
        identity_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerSourceIdentity)
        )
        player_count = await session.scalar(select(text("count(*)")).select_from(Player))

    assert identity_count == 2
    assert player_count == 2


@pytest.mark.asyncio
async def test_same_source_and_exact_same_id_reuses_one_identity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(session, [sample_player(source_player_id="same-id")])
        await import_players(session, [sample_player(source_player_id="same-id")])

    async with session_factory() as session:
        identity_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerSourceIdentity)
        )
        projection_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerProjection)
        )

    assert identity_count == 1
    assert projection_count == 2


@pytest.mark.asyncio
async def test_same_source_ids_differing_by_case_create_separate_identities(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(session, [sample_player(source_player_id="case-id")])
        await import_players(session, [sample_player(source_player_id="CASE-ID")])

    async with session_factory() as session:
        identities = list(
            await session.scalars(
                select(PlayerSourceIdentity.source_player_id).order_by(
                    PlayerSourceIdentity.source_player_id
                )
            )
        )
        player_count = await session.scalar(select(text("count(*)")).select_from(Player))

    assert identities == ["CASE-ID", "case-id"]
    assert player_count == 1


@pytest.mark.asyncio
async def test_different_sources_may_reuse_same_source_player_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(
            session,
            [sample_player(source_player_id="shared-id", full_name="Shared Player")],
            metadata=metadata(source_key="source-a", source_name="Source A"),
        )
        await import_players(
            session,
            [sample_player(source_player_id="shared-id", full_name="Shared Player")],
            metadata=metadata(source_key="source-b", source_name="Source B"),
        )

    async with session_factory() as session:
        identity_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerSourceIdentity)
        )
        player_count = await session.scalar(select(text("count(*)")).select_from(Player))

    assert identity_count == 2
    assert player_count == 1


@pytest.mark.asyncio
async def test_ambiguous_exact_name_fallback_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                Player(full_name="Ambiguous Player"),
                Player(full_name="Ambiguous Player"),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(ProjectionProviderValidationError, match="ambiguous"):
            await import_players(
                session,
                [sample_player(source_player_id="ambiguous-id", full_name="Ambiguous Player")],
            )

    async with session_factory() as session:
        identity_count = await session.scalar(
            select(text("count(*)")).select_from(PlayerSourceIdentity)
        )
        player_count = await session.scalar(select(text("count(*)")).select_from(Player))

    assert identity_count == 0
    assert player_count == 2


@pytest.mark.asyncio
async def test_import_rollback_on_validation_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ProjectionProviderValidationError, match="source_name"):
            await import_players(
                session,
                [sample_player()],
                metadata=metadata(source_name=" "),
            )

    async with session_factory() as session:
        assert await session.scalar(select(text("count(*)")).select_from(ProjectionSet)) == 0
        assert await session.scalar(select(text("count(*)")).select_from(Player)) == 0


@pytest.mark.asyncio
async def test_import_rollback_on_database_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(Exception):
            await import_players(
                session,
                [sample_player(fgm=Decimal("4.000"), fga=Decimal("3.000"))],
            )

    async with session_factory() as session:
        assert await session.scalar(select(text("count(*)")).select_from(ProjectionSet)) == 0
        assert await session.scalar(select(text("count(*)")).select_from(PlayerProjection)) == 0
        assert await session.scalar(select(text("count(*)")).select_from(Player)) == 0


@pytest.mark.asyncio
async def test_empty_import_and_missing_source_metadata_fail(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ProjectionProviderValidationError, match="at least one player"):
            await import_players(session, [])
        with pytest.raises(ProjectionProviderValidationError, match="source_key"):
            await import_players(
                session,
                [sample_player()],
                metadata=metadata(source_key=" "),
            )


@pytest.mark.asyncio
async def test_draft_remains_pinned_after_new_active_projection_set(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_players(
            session,
            [sample_player()],
            metadata=metadata(activate=True),
        )
        await create_league_and_draft(session, first.projection_set_id)
        second = await import_players(
            session,
            [sample_player(source_player_id="2", full_name="New Active Player")],
            metadata=metadata(as_of_date=date(2026, 10, 9), activate=True),
        )

    async with session_factory() as session:
        draft = await session.scalar(select(DraftSession))
        first_set = await session.get(ProjectionSet, first.projection_set_id)
        second_set = await session.get(ProjectionSet, second.projection_set_id)

    assert draft is not None
    assert draft.projection_set_id == first.projection_set_id
    assert first_set is not None
    assert second_set is not None
    assert first_set.is_active is False
    assert second_set.is_active is True


@pytest.mark.asyncio
async def test_activation_is_scoped_to_source_season_and_projection_type(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_players(
            session,
            [sample_player(source_player_id="1", full_name="Source A First")],
            metadata=metadata(source_key="source-a", source_name="Source A", activate=True),
        )
        await import_players(
            session,
            [sample_player(source_player_id="2", full_name="Source A Second")],
            metadata=metadata(
                source_key="source-a",
                source_name="Source A",
                as_of_date=date(2026, 10, 9),
                activate=True,
            ),
        )
        await import_players(
            session,
            [sample_player(source_player_id="1", full_name="Source B First")],
            metadata=metadata(source_key="source-b", source_name="Source B", activate=True),
        )

    async with session_factory() as session:
        active_set_count = await session.scalar(
            select(text("count(*)")).select_from(ProjectionSet).where(
                ProjectionSet.is_active.is_(True)
            )
        )

    assert active_set_count == 2


@pytest.mark.asyncio
async def test_projection_set_read_response_includes_player_count_and_metadata(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        result = await import_players(session, [sample_player()])

    response = await client.get(f"/projection-sets/{result.projection_set_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == result.projection_set_id
    assert body["source"]["key"] == "manual"
    assert body["season"] == 2026
    assert body["as_of_date"] == "2026-10-08"
    assert body["imported_at"]
    assert body["is_active"] is False
    assert body["player_count"] == 1


async def import_players(
    session: AsyncSession,
    players: list[ProjectionPlayer],
    metadata: ProjectionImportMetadata | None = None,
):
    return await ProjectionImportService(session).import_players(
        players=players,
        metadata=metadata or globals()["metadata"](),
    )


def metadata(
    *,
    source_key: str = "manual",
    source_name: str = "Manual Source",
    as_of_date: date = date(2026, 10, 8),
    activate: bool = False,
) -> ProjectionImportMetadata:
    return ProjectionImportMetadata(
        source_key=source_key,
        source_name=source_name,
        source_description="Test import source",
        season=2026,
        as_of_date=as_of_date,
        activate=activate,
        notes="Test immutable import",
    )


def sample_player(
    *,
    source_player_id: str = "source-1",
    full_name: str = "Imported Player",
    team: str = "DEN",
    positions: tuple[str, ...] = ("C",),
    games: Decimal = Decimal("70.50"),
    fgm: Decimal = Decimal("3.000"),
    fga: Decimal = Decimal("8.000"),
) -> ProjectionPlayer:
    return ProjectionPlayer(
        source_player_id=source_player_id,
        full_name=full_name,
        team=team,
        primary_position=positions[0],
        positions=positions,
        games=games,
        minutes_per_game=Decimal("31.25"),
        fgm=fgm,
        fga=fga,
        ftm=Decimal("2.000"),
        fta=Decimal("3.000"),
        rebounds=Decimal("9.000"),
        assists=Decimal("4.000"),
        steals=Decimal("1.000"),
        blocks=Decimal("1.000"),
        turnovers=Decimal("2.000"),
    )


async def create_league_and_draft(
    session: AsyncSession,
    projection_set_id: int,
) -> None:
    session.add(
        League(
            id=1,
            name="Import Test League",
            platform="ESPN",
            season=2026,
            team_count=12,
            scoring_format="points",
            acquisition_limit_per_day=None,
            playoff_team_count=8,
        )
    )
    await session.flush()
    session.add(
        DraftSession(
            league_id=1,
            projection_set_id=projection_set_id,
            name="Pinned Draft",
            season=2026,
            draft_type="snake",
            status="in_progress",
            team_count=12,
            rounds=14,
        )
    )
    await session.commit()


async def eligibility_positions(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[str]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(PlayerEligibility.position_key).order_by(
                    PlayerEligibility.position_key
                )
            )
        )


def load_projection_import_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260724_0005_add_projection_import_identity.py"
    )
    spec = importlib.util.spec_from_file_location(
        "projection_import_identity_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load projection import identity migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
