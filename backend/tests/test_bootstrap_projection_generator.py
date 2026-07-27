from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from uuid import uuid4

from app.projections.bootstrap.assumptions import (
    BootstrapAssumptions,
    PlayerBootstrapOverride,
)
from app.projections.bootstrap.basketball_reference import (
    parse_basketball_reference_metadata_csv,
    parse_basketball_reference_sps_csv,
)
from app.projections.bootstrap.generator import (
    default_basketball_reference_sps_path,
    generate_bootstrap_projection_payload,
    generate_projection_player,
)
from app.projections.import_service import ProjectionImportMetadata, ProjectionImportService
from app.projections.model import ProjectionSet
from app.players.model import Player, PlayerEligibility
from app.shared.config.settings import get_settings
from app.shared.database.base import Base


SPS_HEADER = (
    ",,,Per 36 Minutes,Per 36 Minutes,Per 36 Minutes,Per 36 Minutes,"
    "Per 36 Minutes,Per 36 Minutes,Per 36 Minutes,Per 36 Minutes,"
    "Per 36 Minutes,Per 36 Minutes,Per 36 Minutes,Per 36 Minutes,"
    "Per 36 Minutes,Per 36 Minutes,Shooting,Shooting,Shooting,-additional\n"
    "Rk,Player,Type,FG,FGA,3P,3PA,FT,FTA,ORB,TRB,AST,STL,BLK,TOV,"
    "PF,PTS,FG%,3P%,FT%,-9999\n"
)


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


def test_basketball_reference_sps_parser_reads_typed_players(tmp_path: Path) -> None:
    csv_path = write_sps_csv(
        tmp_path,
        "1,Example Player,Projected,6.1,11.7,0.6,2.0,1.6,2.7,3.5,"
        "10.0,2.1,1.3,1.1,1.4,2.6,14.4,.519,.292,.585,example01\n",
    )

    result = parse_basketball_reference_sps_csv(csv_path)

    assert result.rows_read == 1
    assert result.rejected_issues == ()
    assert result.accepted_players[0].source_player_id == "example01"
    assert result.accepted_players[0].full_name == "Example Player"
    assert result.accepted_players[0].fg_per36 == Decimal("6.1")
    assert result.accepted_players[0].points_per36 == Decimal("14.4")


def test_parser_reports_invalid_numeric_values(tmp_path: Path) -> None:
    csv_path = write_sps_csv(
        tmp_path,
        "1,Invalid Player,Projected,bad,11.7,0.6,2.0,1.6,2.7,3.5,"
        "10.0,2.1,1.3,1.1,1.4,2.6,14.4,.519,.292,.585,invalid01\n",
    )

    result = parse_basketball_reference_sps_csv(csv_path)

    assert result.accepted_players == ()
    assert result.invalid_numeric_values == 1
    assert result.rejected_issues[0].code == "invalid_numeric"
    assert result.rejected_issues[0].field == "FG"


def test_parser_reports_duplicate_basketball_reference_ids(tmp_path: Path) -> None:
    csv_path = write_sps_csv(
        tmp_path,
        "1,First Player,Projected,6,12,1,3,2,3,1,8,4,1,1,2,2,15,.5,.3,.7,dup01\n"
        "2,Second Player,Projected,6,12,1,3,2,3,1,8,4,1,1,2,2,15,.5,.3,.7,dup01\n",
    )

    result = parse_basketball_reference_sps_csv(csv_path)

    assert len(result.accepted_players) == 1
    assert result.duplicate_ids == 1
    assert result.rejected_issues[0].code == "duplicate_basketball_reference_id"


def test_metadata_parser_normalizes_team_and_positions(tmp_path: Path) -> None:
    result = parse_basketball_reference_metadata_csv(
        write_metadata_csv(tmp_path, "example01,Example Player, den , c , C\n")
    )

    assert result.rows_read == 1
    assert result.rejected_issues == ()
    metadata = result.accepted_metadata[0]
    assert metadata.source_player_id == "example01"
    assert metadata.team == "DEN"
    assert metadata.primary_position == "C"
    assert metadata.positions == ("C",)


def test_metadata_parser_preserves_multi_position_eligibility(tmp_path: Path) -> None:
    result = parse_basketball_reference_metadata_csv(
        write_metadata_csv(tmp_path, 'combo01,Combo Guard,OKC,PG,"PG,SG"\n')
    )

    assert result.accepted_metadata[0].positions == ("PG", "SG")


def test_metadata_parser_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    result = parse_basketball_reference_metadata_csv(
        write_metadata_csv(
            tmp_path,
            "dup01,First Player,DEN,C,C\n"
            "dup01,Second Player,OKC,PG,PG\n",
        )
    )

    assert result.duplicate_ids == 1
    assert result.rejected_issues[0].code == "duplicate_metadata_source_id"


def test_metadata_parser_rejects_invalid_positions(tmp_path: Path) -> None:
    result = parse_basketball_reference_metadata_csv(
        write_metadata_csv(tmp_path, "bad01,Bad Position,DEN,W,W\n")
    )

    assert result.invalid_positions == 2
    assert {issue.code for issue in result.rejected_issues} == {"invalid_position"}


def test_projection_generation_uses_default_assumptions(tmp_path: Path) -> None:
    payload = generate_bootstrap_projection_payload(
        write_sps_csv(
            tmp_path,
            "1,Default Player,Projected,18,36,0,0,9,18,0,9,6,3,1.8,3.6,2,45,.5,.3,.5,default01\n",
        ),
        write_metadata_csv(tmp_path, "default01,Default Player,DEN,C,C\n"),
    )

    player = payload.players[0]

    assert payload.diagnostics.players_using_default_assumptions == 1
    assert player.games == Decimal("68.00")
    assert player.minutes_per_game == Decimal("26.00")
    assert player.fgm == Decimal("13.000")
    assert player.fga == Decimal("26.000")
    assert player.ftm == Decimal("6.500")
    assert player.rebounds == Decimal("6.500")
    assert player.assists == Decimal("4.333")
    assert player.steals == Decimal("2.167")
    assert player.blocks == Decimal("1.300")
    assert player.turnovers == Decimal("2.600")
    assert player.team == "DEN"
    assert player.primary_position == "C"
    assert player.positions == ("C",)


def test_projection_generation_uses_player_overrides(tmp_path: Path) -> None:
    result = parse_basketball_reference_sps_csv(
        write_sps_csv(
            tmp_path,
            "1,Override Player,Projected,18,36,0,0,9,18,0,9,6,3,1.8,3.6,2,45,.5,.3,.5,override01\n",
        )
    )
    assumptions = BootstrapAssumptions(
        player_overrides={
            "override01": PlayerBootstrapOverride(
                projected_games=Decimal("72"),
                minutes_per_game=Decimal("30"),
            )
        }
    )

    player = generate_projection_player(result.accepted_players[0], assumptions)

    assert player.games == Decimal("72.00")
    assert player.minutes_per_game == Decimal("30.00")
    assert player.fgm == Decimal("15.000")


@pytest.mark.asyncio
async def test_bootstrap_projection_import_integration(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    payload = generate_bootstrap_projection_payload(
        write_sps_csv(
            tmp_path,
            "1,Import Player,Projected,6,12,1,3,2,3,1,8,4,1,1,2,2,15,.5,.3,.7,import01\n",
        ),
        write_metadata_csv(tmp_path, "import01,Import Player,OKC,PG,\"PG,SG\"\n"),
    )
    metadata = ProjectionImportMetadata(
        source_key="br-bootstrap-test",
        source_name="Basketball Reference Bootstrap Test",
        source_description="Test bootstrap source",
        season=2027,
        as_of_date=date(2026, 7, 26),
        activate=True,
    )

    async with session_factory() as session:
        preview = await ProjectionImportService(session).preview_players(
            players=payload.players,
            metadata=metadata,
            rows_read=payload.diagnostics.rows_read,
        )
    async with session_factory() as session:
        result = await ProjectionImportService(session).import_players(
            players=payload.players,
            metadata=metadata,
            rows_read=payload.diagnostics.rows_read,
        )

    async with session_factory() as session:
        projection_set = await session.get(ProjectionSet, result.projection_set_id)
        player = await session.scalar(select(Player).where(Player.full_name == "Import Player"))
        eligibilities = list(
            await session.scalars(
                select(PlayerEligibility.position_key)
                .where(PlayerEligibility.player_id == player.id)
                .order_by(PlayerEligibility.position_key)
            )
        )

    assert preview.valid_player_rows == 1
    assert preview.eligibility_positions_to_add == 2
    assert result.projection_rows_created == 1
    assert projection_set is not None
    assert projection_set.is_active is True
    assert player is not None
    assert player.team == "OKC"
    assert player.primary_position == "PG"
    assert eligibilities == ["PG", "SG"]


def test_actual_basketball_reference_sps_csv_parses_when_present() -> None:
    csv_path = default_basketball_reference_sps_path()
    if not csv_path.exists():
        pytest.skip("local Basketball Reference SPS CSV is not present")

    payload = generate_bootstrap_projection_payload(csv_path)

    assert payload.diagnostics.rows_read > 0
    if not payload.diagnostics.metadata_available:
        pytest.skip("local Basketball Reference metadata CSV is not present")
    assert payload.diagnostics.accepted_players > 0
    assert len(payload.players) == payload.diagnostics.accepted_players


def test_projection_payload_reports_missing_metadata(tmp_path: Path) -> None:
    payload = generate_bootstrap_projection_payload(
        write_sps_csv(
            tmp_path,
            "1,Missing Metadata,Projected,6,12,1,3,2,3,1,8,4,1,1,2,2,15,.5,.3,.7,missing01\n",
        ),
        write_metadata_csv(tmp_path, "other01,Other Player,DEN,C,C\n"),
    )

    assert payload.players == []
    assert payload.diagnostics.players_missing_metadata == 1
    assert payload.diagnostics.rejected_players == 1


def write_sps_csv(tmp_path: Path, rows: str) -> Path:
    csv_path = tmp_path / "basketball_reference_sps.csv"
    csv_path.write_text(SPS_HEADER + rows, encoding="utf-8")
    return csv_path


def write_metadata_csv(tmp_path: Path, rows: str) -> Path:
    csv_path = tmp_path / "basketball_reference_player_metadata.csv"
    csv_path.write_text(
        "source_player_id,player_name,team,primary_position,positions\n" + rows,
        encoding="utf-8",
    )
    return csv_path
