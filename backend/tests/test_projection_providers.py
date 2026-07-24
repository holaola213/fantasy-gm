from __future__ import annotations

from decimal import Decimal

import pytest

from app.projections.providers import (
    CSVProjectionProvider,
    ProjectionPlayer,
    ProjectionProviderService,
    ProjectionProviderValidationError,
    SeedProjectionProvider,
)


CSV_HEADER = (
    "player_id,full_name,team,primary_position,positions,games,minutes_per_game,"
    "fgm,fga,ftm,fta,rebounds,assists,steals,blocks,turnovers,is_active\n"
)


def test_projection_provider_service_uses_injected_provider() -> None:
    expected = sample_player(source_player_id="local-1", full_name="Injected Player")

    class FakeProvider:
        def load_players(self) -> list[ProjectionPlayer]:
            return [expected]

    service = ProjectionProviderService(default_provider=FakeProvider())

    assert service.load_players() == [expected]


def test_csv_provider_loads_normalized_players(tmp_path) -> None:
    csv_path = tmp_path / "projections.csv"
    csv_path.write_text(
        CSV_HEADER
        + " 101 , Nikola Jokic , den , c , c , 70.5 , 34.2 , 10.8 , 18.9 , "
        "5.1 , 6.3 , 12.4 , 9.2 , 1.4 , 0.9 , 3.1 , yes\n",
        encoding="utf-8",
    )

    players = CSVProjectionProvider(csv_path).load_players()

    assert players == [
        ProjectionPlayer(
            source_player_id="101",
            full_name="Nikola Jokic",
            team="DEN",
            primary_position="C",
            positions=("C",),
            games=Decimal("70.5"),
            minutes_per_game=Decimal("34.2"),
            fgm=Decimal("10.8"),
            fga=Decimal("18.9"),
            ftm=Decimal("5.1"),
            fta=Decimal("6.3"),
            rebounds=Decimal("12.4"),
            assists=Decimal("9.2"),
            steals=Decimal("1.4"),
            blocks=Decimal("0.9"),
            turnovers=Decimal("3.1"),
            is_active=True,
        )
    ]


def test_csv_provider_reports_missing_required_columns(tmp_path) -> None:
    csv_path = tmp_path / "missing.csv"
    csv_path.write_text("player_id,full_name\n1,Player One\n", encoding="utf-8")

    with pytest.raises(ProjectionProviderValidationError, match="missing required"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_reports_empty_files(tmp_path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(ProjectionProviderValidationError, match="empty"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_reports_invalid_numeric_values(tmp_path) -> None:
    csv_path = tmp_path / "invalid_numeric.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,C,C,not-a-number,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError, match="games"):
        CSVProjectionProvider(csv_path).load_players()


def test_csv_provider_detects_duplicates_after_normalization(tmp_path) -> None:
    csv_path = tmp_path / "duplicates.csv"
    csv_path.write_text(
        CSV_HEADER
        + " abc , Player One,DEN,C,C,70,30,1,2,1,2,3,4,1,1,2,true\n"
        + " ABC , player one ,OKC,PG,PG,70,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError) as exc_info:
        CSVProjectionProvider(csv_path).load_players()

    message = str(exc_info.value)
    assert "duplicate player_id" in message
    assert "duplicate full_name" in message


def test_csv_provider_reports_malformed_positions(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    csv_path.write_text(
        CSV_HEADER
        + "1,Player One,DEN,PG,PG|IR,70,30,1,2,1,2,3,4,1,1,2,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectionProviderValidationError, match="unsupported"):
        CSVProjectionProvider(csv_path).load_players()


def test_seed_provider_loads_deterministic_development_players() -> None:
    players = SeedProjectionProvider().load_players()

    assert len(players) >= 10
    assert players[0].source_player_id == "1"
    assert players[0].full_name == "Nikola Jokic"
    assert players[0].positions == ("C",)
    assert players[0].games == Decimal("70.50")


def sample_player(
    *,
    source_player_id: str = "1",
    full_name: str = "Sample Player",
) -> ProjectionPlayer:
    return ProjectionPlayer(
        source_player_id=source_player_id,
        full_name=full_name,
        team="DEN",
        primary_position="C",
        positions=("C",),
        games=Decimal("70"),
        minutes_per_game=Decimal("30"),
        fgm=Decimal("1"),
        fga=Decimal("2"),
        ftm=Decimal("1"),
        fta=Decimal("2"),
        rebounds=Decimal("3"),
        assists=Decimal("4"),
        steals=Decimal("1"),
        blocks=Decimal("1"),
        turnovers=Decimal("2"),
    )
